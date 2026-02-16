from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from main import app
from modules.cadastro.infrastructure import models as cadastro_models  # noqa: F401
from modules.estoque_retalhos.infrastructure import models as estoque_models  # noqa: F401

ADMIN_HEADERS = {"X-User-Role": "admin"}
OPERADOR_HEADERS = {"X-User-Role": "operador"}


@pytest.fixture
def client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def _create_insumo(client: TestClient, *, codigo: str, descricao: str, unidade: str = "M2") -> dict:
    response = client.post(
        "/api/v1/cadastro/insumos",
        headers=ADMIN_HEADERS,
        json={
            "codigo": codigo,
            "descricao": descricao,
            "categoria": "CHAPA",
            "unidade_medida": unidade,
            "custo_unitario": "100.00",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_lote(
    client: TestClient,
    *,
    insumo_id: int,
    codigo_lote: str,
    quantidade: str,
    custo_total: str = "0",
) -> dict:
    response = client.post(
        "/api/v1/estoque-retalhos/lotes",
        headers=ADMIN_HEADERS,
        json={
            "insumo_id": insumo_id,
            "codigo_lote": codigo_lote,
            "quantidade_inicial": quantidade,
            "custo_total": custo_total,
            "largura_mm": "2000",
            "altura_mm": "1000",
            "espessura_mm": "2",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_entrada_lote_e_saldo_por_insumo(client: TestClient) -> None:
    insumo = _create_insumo(client, codigo="INS-EST-001", descricao="Chapa Aco 2mm")
    lote = _create_lote(
        client,
        insumo_id=insumo["id"],
        codigo_lote="L-001",
        quantidade="10",
        custo_total="500",
    )

    assert float(lote["quantidade_disponivel"]) == 10.0
    assert lote["is_retalho"] is False

    lotes = client.get(
        "/api/v1/estoque-retalhos/lotes?com_saldo=true",
        headers=ADMIN_HEADERS,
    )
    assert lotes.status_code == 200
    assert lotes.json()["meta"]["total"] == 1

    saldos = client.get("/api/v1/estoque-retalhos/saldos/insumos", headers=ADMIN_HEADERS)
    assert saldos.status_code == 200
    assert len(saldos.json()) == 1
    assert float(saldos.json()[0]["saldo_disponivel"]) == 10.0
    assert saldos.json()[0]["lotes_com_saldo"] == 1


def test_consumo_ajuste_e_extrato_de_movimentacoes(client: TestClient) -> None:
    insumo = _create_insumo(client, codigo="INS-EST-002", descricao="Chapa Aluminio")
    lote = _create_lote(client, insumo_id=insumo["id"], codigo_lote="L-002", quantidade="10")

    consumo = client.post(
        f"/api/v1/estoque-retalhos/lotes/{lote['id']}/consumos",
        headers=OPERADOR_HEADERS,
        json={"quantidade": "3", "ordem_id": 123, "observacao": "Consumo em OP"},
    )
    assert consumo.status_code == 200
    assert float(consumo.json()["quantidade_disponivel"]) == 7.0

    ajuste = client.post(
        f"/api/v1/estoque-retalhos/lotes/{lote['id']}/ajustes",
        headers=ADMIN_HEADERS,
        json={"delta_quantidade": "-2", "observacao": "Avaria em material"},
    )
    assert ajuste.status_code == 200
    assert float(ajuste.json()["quantidade_disponivel"]) == 5.0

    extrato = client.get(
        f"/api/v1/estoque-retalhos/lotes/{lote['id']}/movimentacoes",
        headers=ADMIN_HEADERS,
    )
    assert extrato.status_code == 200
    tipos = {item["tipo_movimento"] for item in extrato.json()["items"]}
    assert {"ENTRADA", "CONSUMO_OP", "AJUSTE"}.issubset(tipos)


def test_geracao_e_consumo_de_retalho(client: TestClient) -> None:
    insumo = _create_insumo(client, codigo="INS-EST-003", descricao="Chapa Inox")
    lote_origem = _create_lote(
        client,
        insumo_id=insumo["id"],
        codigo_lote="L-003",
        quantidade="20",
        custo_total="200",
    )

    retalho = client.post(
        f"/api/v1/estoque-retalhos/lotes/{lote_origem['id']}/retalhos",
        headers=OPERADOR_HEADERS,
        json={
            "codigo_lote_retalho": "RET-003-A",
            "quantidade": "5",
            "largura_mm": "600",
            "altura_mm": "300",
        },
    )
    assert retalho.status_code == 200
    body = retalho.json()
    assert float(body["lote_origem"]["quantidade_disponivel"]) == 15.0
    assert body["lote_retalho"]["is_retalho"] is True
    assert body["lote_retalho"]["lote_origem_id"] == lote_origem["id"]

    consumo_retalho = client.post(
        f"/api/v1/estoque-retalhos/lotes/{body['lote_retalho']['id']}/consumos",
        headers=OPERADOR_HEADERS,
        json={"quantidade": "2"},
    )
    assert consumo_retalho.status_code == 200
    assert float(consumo_retalho.json()["quantidade_disponivel"]) == 3.0

    extrato_retalho = client.get(
        f"/api/v1/estoque-retalhos/lotes/{body['lote_retalho']['id']}/movimentacoes",
        headers=ADMIN_HEADERS,
    )
    assert extrato_retalho.status_code == 200
    tipos = [item["tipo_movimento"] for item in extrato_retalho.json()["items"]]
    assert "RETALHO_CONSUMIDO" in tipos


def test_nao_permite_consumo_acima_do_saldo(client: TestClient) -> None:
    insumo = _create_insumo(client, codigo="INS-EST-004", descricao="Chapa Galvanizada")
    lote = _create_lote(client, insumo_id=insumo["id"], codigo_lote="L-004", quantidade="2")

    consumo = client.post(
        f"/api/v1/estoque-retalhos/lotes/{lote['id']}/consumos",
        headers=OPERADOR_HEADERS,
        json={"quantidade": "3"},
    )
    assert consumo.status_code == 409
    assert "Saldo insuficiente" in consumo.json()["detail"]
