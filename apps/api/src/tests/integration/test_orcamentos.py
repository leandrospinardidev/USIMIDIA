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
from modules.orcamentos.infrastructure import models as orc_models  # noqa: F401

ADMIN_HEADERS = {"X-User-Role": "admin"}


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
        json={"codigo": "CLI-ORC-01", "razao_social": "Cliente Orcamentos LTDA"},
    )
    assert response.status_code == 201
    return response.json()


def _create_produto(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/cadastro/produtos-finais",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "PRD-ORC-01",
            "descricao": "Equipamento Industrial A",
            "unidade_medida": "UN",
            "margem_lucro_padrao_pct": "25.00",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_insumo(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/cadastro/insumos",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "INS-ORC-01",
            "descricao": "Chapa Aco Carbono",
            "categoria": "CHAPA",
            "unidade_medida": "UN",
            "custo_unitario": "10.00",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_centro(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/cadastro/centros-trabalho",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "CT-ORC-01",
            "nome": "Router CNC Orcamento",
            "tipo_maquina": "ROUTER_CNC",
            "taxa_horaria": "120.00",
            "setup_padrao_min": 15,
            "capacidade_horas_dia": "8",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_bom_base(client: TestClient, *, produto_id: int, insumo_id: int) -> dict:
    bom = client.post(
        "/api/v1/engenharia-bom/boms",
        headers=ADMIN_HEADERS,
        json={"produto_final_id": produto_id},
    )
    assert bom.status_code == 201
    bom_data = bom.json()

    add_item = client.post(
        f"/api/v1/engenharia-bom/boms/{bom_data['id']}/itens",
        headers=ADMIN_HEADERS,
        json={
            "item_tipo": "INSUMO",
            "insumo_id": insumo_id,
            "quantidade": "2",
            "perda_pct": "10",
        },
    )
    assert add_item.status_code == 201
    return bom_data


def test_simulacao_orcamento_calcula_material_maquina_margem(client: TestClient) -> None:
    cliente = _create_cliente(client)
    produto = _create_produto(client)
    insumo = _create_insumo(client)
    centro = _create_centro(client)
    bom = _create_bom_base(client, produto_id=produto["id"], insumo_id=insumo["id"])

    simulacao = client.post(
        "/api/v1/orcamentos/simulacoes",
        headers=ADMIN_HEADERS,
        json={
            "cliente_id": cliente["id"],
            "produto_final_id": produto["id"],
            "bom_id": bom["id"],
            "quantidade": "3",
            "margem_lucro_pct": "20",
            "custo_indireto_fixo": "10",
            "custo_indireto_pct": "5",
            "operacoes": [
                {
                    "centro_trabalho_id": centro["id"],
                    "setup_min": "30",
                    "ciclo_min": "10",
                }
            ],
        },
    )
    assert simulacao.status_code == 200
    body = simulacao.json()

    assert body["bom_id"] == bom["id"]
    assert len(body["materiais"]) == 1
    assert len(body["operacoes"]) == 1
    assert float(body["custo_material_total"]) == pytest.approx(66.0)
    assert float(body["custo_maquina_total"]) == pytest.approx(120.0)
    assert float(body["custo_indireto_total"]) == pytest.approx(19.3)
    assert float(body["preco_venda"]) == pytest.approx(246.36)


def test_orcamento_versionado_e_status(client: TestClient) -> None:
    cliente = _create_cliente(client)
    produto = _create_produto(client)
    insumo = _create_insumo(client)
    centro = _create_centro(client)
    bom = _create_bom_base(client, produto_id=produto["id"], insumo_id=insumo["id"])

    create_orc = client.post(
        "/api/v1/orcamentos",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "ORC-TEST-001",
            "cliente_id": cliente["id"],
            "produto_final_id": produto["id"],
            "bom_id": bom["id"],
            "quantidade": "2",
            "margem_lucro_pct": "20",
            "custo_indireto_fixo": "10",
            "custo_indireto_pct": "5",
            "operacoes": [
                {
                    "centro_trabalho_id": centro["id"],
                    "setup_min": "20",
                    "ciclo_min": "8",
                    "descricao": "Usinagem CNC",
                }
            ],
        },
    )
    assert create_orc.status_code == 201
    orc = create_orc.json()
    assert orc["codigo"] == "ORC-TEST-001"
    assert orc["status"] == "RASCUNHO"
    assert len(orc["versoes"]) == 1
    assert orc["versoes"][0]["versao"] == 1

    nova_versao = client.post(
        f"/api/v1/orcamentos/{orc['id']}/versoes",
        headers=ADMIN_HEADERS,
        json={
            "bom_id": bom["id"],
            "quantidade": "4",
            "margem_lucro_pct": "30",
            "custo_indireto_fixo": "5",
            "custo_indireto_pct": "8",
            "operacoes": [
                {
                    "centro_trabalho_id": centro["id"],
                    "setup_min": "20",
                    "ciclo_min": "8",
                }
            ],
        },
    )
    assert nova_versao.status_code == 200
    orc_updated = nova_versao.json()
    assert len(orc_updated["versoes"]) == 2
    assert orc_updated["versoes"][0]["versao"] == 2

    listagem = client.get("/api/v1/orcamentos?search=ORC-TEST-001", headers=ADMIN_HEADERS)
    assert listagem.status_code == 200
    assert listagem.json()["meta"]["total"] == 1
    assert listagem.json()["items"][0]["versao_atual"] == 2

    status_update = client.patch(
        f"/api/v1/orcamentos/{orc['id']}/status",
        headers=ADMIN_HEADERS,
        json={"status": "ENVIADO"},
    )
    assert status_update.status_code == 200
    assert status_update.json()["status"] == "ENVIADO"
