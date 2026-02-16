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


def _create_produto(client: TestClient, *, codigo: str, descricao: str) -> dict:
    response = client.post(
        "/api/v1/cadastro/produtos-finais",
        headers=ADMIN_HEADERS,
        json={"codigo": codigo, "descricao": descricao, "unidade_medida": "UN"},
    )
    assert response.status_code == 201
    return response.json()


def _create_insumo(
    client: TestClient,
    *,
    codigo: str,
    descricao: str,
    unidade: str,
    custo_unitario: str,
) -> dict:
    response = client.post(
        "/api/v1/cadastro/insumos",
        headers=ADMIN_HEADERS,
        json={
            "codigo": codigo,
            "descricao": descricao,
            "categoria": "OUTRO",
            "unidade_medida": unidade,
            "custo_unitario": custo_unitario,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_bom_versionamento_e_ativacao_unica_por_produto(client: TestClient) -> None:
    produto = _create_produto(client, codigo="PRD-A", descricao="Modulo Principal")

    bom_v1 = client.post(
        "/api/v1/engenharia-bom/boms",
        headers=ADMIN_HEADERS,
        json={"produto_final_id": produto["id"]},
    )
    assert bom_v1.status_code == 201
    body_v1 = bom_v1.json()
    assert body_v1["versao"] == 1
    assert body_v1["status"] == "RASCUNHO"

    ativar_v1 = client.patch(
        f"/api/v1/engenharia-bom/boms/{body_v1['id']}",
        headers=ADMIN_HEADERS,
        json={"status": "ATIVA"},
    )
    assert ativar_v1.status_code == 200
    assert ativar_v1.json()["status"] == "ATIVA"

    bom_v2 = client.post(
        "/api/v1/engenharia-bom/boms",
        headers=ADMIN_HEADERS,
        json={"produto_final_id": produto["id"], "status": "ATIVA"},
    )
    assert bom_v2.status_code == 201
    body_v2 = bom_v2.json()
    assert body_v2["versao"] == 2
    assert body_v2["status"] == "ATIVA"

    v1_after = client.get(
        f"/api/v1/engenharia-bom/boms/{body_v1['id']}",
        headers=ADMIN_HEADERS,
    )
    assert v1_after.status_code == 200
    assert v1_after.json()["status"] == "OBSOLETA"

    list_response = client.get(
        f"/api/v1/engenharia-bom/boms?produto_final_id={produto['id']}",
        headers=ADMIN_HEADERS,
    )
    assert list_response.status_code == 200
    assert list_response.json()["meta"]["total"] == 2


def test_bom_anti_ciclo_e_explosao_de_insumos(client: TestClient) -> None:
    produto_a = _create_produto(client, codigo="PRD-MAQ-A", descricao="Maquina A")
    produto_b = _create_produto(client, codigo="PRD-SUB-B", descricao="Subconjunto B")
    insumo_a = _create_insumo(
        client,
        codigo="INS-BASE-A",
        descricao="Base da maquina",
        unidade="UN",
        custo_unitario="10.00",
    )
    insumo_b = _create_insumo(
        client,
        codigo="INS-SUB-B",
        descricao="Peca do subconjunto",
        unidade="UN",
        custo_unitario="2.00",
    )

    bom_a = client.post(
        "/api/v1/engenharia-bom/boms",
        headers=ADMIN_HEADERS,
        json={"produto_final_id": produto_a["id"]},
    )
    assert bom_a.status_code == 201
    bom_a_id = bom_a.json()["id"]

    add_a_insumo = client.post(
        f"/api/v1/engenharia-bom/boms/{bom_a_id}/itens",
        headers=ADMIN_HEADERS,
        json={
            "item_tipo": "INSUMO",
            "insumo_id": insumo_a["id"],
            "quantidade": "3",
        },
    )
    assert add_a_insumo.status_code == 201

    add_a_sub_b = client.post(
        f"/api/v1/engenharia-bom/boms/{bom_a_id}/itens",
        headers=ADMIN_HEADERS,
        json={
            "item_tipo": "SUBCONJUNTO",
            "produto_filho_id": produto_b["id"],
            "quantidade": "2",
        },
    )
    assert add_a_sub_b.status_code == 201

    bom_b = client.post(
        "/api/v1/engenharia-bom/boms",
        headers=ADMIN_HEADERS,
        json={"produto_final_id": produto_b["id"]},
    )
    assert bom_b.status_code == 201
    bom_b_id = bom_b.json()["id"]

    add_b_insumo = client.post(
        f"/api/v1/engenharia-bom/boms/{bom_b_id}/itens",
        headers=ADMIN_HEADERS,
        json={
            "item_tipo": "INSUMO",
            "insumo_id": insumo_b["id"],
            "quantidade": "5",
        },
    )
    assert add_b_insumo.status_code == 201

    ciclo = client.post(
        f"/api/v1/engenharia-bom/boms/{bom_b_id}/itens",
        headers=ADMIN_HEADERS,
        json={
            "item_tipo": "SUBCONJUNTO",
            "produto_filho_id": produto_a["id"],
            "quantidade": "1",
        },
    )
    assert ciclo.status_code == 422
    assert "Ciclo detectado" in ciclo.json()["detail"]

    tree = client.get(f"/api/v1/engenharia-bom/boms/{bom_a_id}/arvore", headers=ADMIN_HEADERS)
    assert tree.status_code == 200
    assert len(tree.json()["tree"]) == 2

    explosao = client.get(
        f"/api/v1/engenharia-bom/boms/{bom_a_id}/explosao?quantidade_base=2",
        headers=ADMIN_HEADERS,
    )
    assert explosao.status_code == 200

    insumos_result = {row["insumo_id"]: row for row in explosao.json()["insumos"]}
    assert float(insumos_result[insumo_a["id"]]["quantidade_total"]) == 6.0
    assert float(insumos_result[insumo_b["id"]]["quantidade_total"]) == 20.0
    assert float(explosao.json()["custo_total_materiais"]) == 100.0
