from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from main import app
from modules.cadastro.infrastructure import models as cadastro_models  # noqa: F401
from modules.engenharia_bom.infrastructure import models as bom_models  # noqa: F401
from modules.ordens_producao.infrastructure import models as op_models  # noqa: F401

ADMIN_HEADERS = {"X-User-Role": "admin"}
PCP_HEADERS = {"X-User-Role": "pcp"}


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


def _create_cliente(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/cadastro/clientes",
        headers=ADMIN_HEADERS,
        json={"codigo": "CLI-OP-01", "razao_social": "Cliente OP"},
    )
    assert response.status_code == 201
    return response.json()


def _create_produto(client: TestClient, codigo: str = "PRD-OP-01") -> dict:
    response = client.post(
        "/api/v1/cadastro/produtos-finais",
        headers=ADMIN_HEADERS,
        json={"codigo": codigo, "descricao": "Produto para OP", "unidade_medida": "UN"},
    )
    assert response.status_code == 201
    return response.json()


def _create_insumo(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/cadastro/insumos",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "INS-OP-01",
            "descricao": "Insumo para OP",
            "categoria": "OUTRO",
            "unidade_medida": "UN",
            "custo_unitario": "8.00",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_centro(client: TestClient, codigo: str = "CT-OP-01") -> dict:
    response = client.post(
        "/api/v1/cadastro/centros-trabalho",
        headers=ADMIN_HEADERS,
        json={
            "codigo": codigo,
            "nome": "Centro OP",
            "tipo_maquina": "ROUTER_CNC",
            "taxa_horaria": "100.00",
            "setup_padrao_min": 20,
            "capacidade_horas_dia": "8",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_bom(client: TestClient, *, produto_id: int, insumo_id: int) -> dict:
    bom = client.post(
        "/api/v1/engenharia-bom/boms",
        headers=ADMIN_HEADERS,
        json={"produto_final_id": produto_id},
    )
    assert bom.status_code == 201
    bom_data = bom.json()

    item = client.post(
        f"/api/v1/engenharia-bom/boms/{bom_data['id']}/itens",
        headers=ADMIN_HEADERS,
        json={
            "item_tipo": "INSUMO",
            "insumo_id": insumo_id,
            "quantidade": "2",
            "perda_pct": "10",
        },
    )
    assert item.status_code == 201
    return bom_data


def test_emissao_op_com_snapshot_bom_e_operacoes(client: TestClient) -> None:
    cliente = _create_cliente(client)
    produto = _create_produto(client)
    insumo = _create_insumo(client)
    centro = _create_centro(client)
    bom = _create_bom(client, produto_id=produto["id"], insumo_id=insumo["id"])

    create_op = client.post(
        "/api/v1/ordens-producao",
        headers=PCP_HEADERS,
        json={
            "cliente_id": cliente["id"],
            "produto_final_id": produto["id"],
            "bom_id": bom["id"],
            "quantidade_planejada": "5",
            "prioridade": 2,
            "operacoes": [
                {
                    "centro_trabalho_id": centro["id"],
                    "setup_planejado_min": "25",
                    "ciclo_planejado_min": "4",
                }
            ],
        },
    )
    assert create_op.status_code == 201
    op = create_op.json()

    assert op["status"] == "PLANEJADA"
    assert len(op["operacoes"]) == 1
    assert op["operacoes"][0]["sequencia"] == 1
    assert op["bom_snapshot_json"]["bom_id"] == bom["id"]
    materiais = op["bom_snapshot_json"]["materiais_planejados"]
    assert len(materiais) == 1
    assert float(materiais[0]["quantidade_total"]) == pytest.approx(11.0)


def test_fluxo_status_da_op(client: TestClient) -> None:
    produto = _create_produto(client, codigo="PRD-OP-02")
    insumo = _create_insumo(client)
    centro = _create_centro(client, codigo="CT-OP-02")
    bom = _create_bom(client, produto_id=produto["id"], insumo_id=insumo["id"])

    create_op = client.post(
        "/api/v1/ordens-producao",
        headers=PCP_HEADERS,
        json={
            "produto_final_id": produto["id"],
            "bom_id": bom["id"],
            "quantidade_planejada": "2",
            "operacoes": [{"centro_trabalho_id": centro["id"], "ciclo_planejado_min": "3"}],
        },
    )
    assert create_op.status_code == 201
    op = create_op.json()

    for next_status in ["EM_PRODUCAO", "PAUSADA", "EM_PRODUCAO", "FINALIZADA"]:
        response = client.patch(
            f"/api/v1/ordens-producao/{op['id']}/status",
            headers=PCP_HEADERS,
            json={"status": next_status},
        )
        assert response.status_code == 200
        op = response.json()

    assert op["status"] == "FINALIZADA"
    assert op["inicio_real"] is not None
    assert op["fim_real"] is not None


def test_transicao_invalida_retorna_409(client: TestClient) -> None:
    produto = _create_produto(client, codigo="PRD-OP-03")
    insumo = _create_insumo(client)
    bom = _create_bom(client, produto_id=produto["id"], insumo_id=insumo["id"])

    create_op = client.post(
        "/api/v1/ordens-producao",
        headers=PCP_HEADERS,
        json={
            "produto_final_id": produto["id"],
            "bom_id": bom["id"],
            "quantidade_planejada": "1",
        },
    )
    assert create_op.status_code == 201
    op_id = create_op.json()["id"]

    invalid = client.patch(
        f"/api/v1/ordens-producao/{op_id}/status",
        headers=PCP_HEADERS,
        json={"status": "FINALIZADA"},
    )
    assert invalid.status_code == 409
    assert "Transicao de status invalida" in invalid.json()["detail"]


def test_adicionar_operacao_com_sequencia_duplicada_retorna_409(client: TestClient) -> None:
    produto = _create_produto(client, codigo="PRD-OP-04")
    insumo = _create_insumo(client)
    centro = _create_centro(client, codigo="CT-OP-04")
    bom = _create_bom(client, produto_id=produto["id"], insumo_id=insumo["id"])

    create_op = client.post(
        "/api/v1/ordens-producao",
        headers=PCP_HEADERS,
        json={
            "produto_final_id": produto["id"],
            "bom_id": bom["id"],
            "quantidade_planejada": "3",
        },
    )
    assert create_op.status_code == 201
    op_id = create_op.json()["id"]

    first = client.post(
        f"/api/v1/ordens-producao/{op_id}/operacoes",
        headers=PCP_HEADERS,
        json={
            "sequencia": 1,
            "centro_trabalho_id": centro["id"],
            "ciclo_planejado_min": "2",
        },
    )
    assert first.status_code == 200

    duplicate = client.post(
        f"/api/v1/ordens-producao/{op_id}/operacoes",
        headers=PCP_HEADERS,
        json={
            "sequencia": 1,
            "centro_trabalho_id": centro["id"],
            "ciclo_planejado_min": "2",
        },
    )
    assert duplicate.status_code == 409
    assert "Sequencia de operacao ja cadastrada" in duplicate.json()["detail"]
