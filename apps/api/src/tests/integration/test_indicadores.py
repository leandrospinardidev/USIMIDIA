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
from modules.estoque_retalhos.infrastructure import models as estoque_models  # noqa: F401
from modules.mes_apontamentos.infrastructure import models as mes_models  # noqa: F401
from modules.orcamentos.infrastructure import models as orc_models  # noqa: F401
from modules.ordens_producao.infrastructure import models as op_models  # noqa: F401

ADMIN_HEADERS = {"X-User-Role": "admin"}
PCP_HEADERS = {"X-User-Role": "pcp"}
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


def _create_cliente(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/cadastro/clientes",
        headers=ADMIN_HEADERS,
        json={"codigo": "CLI-IND-01", "razao_social": "Cliente Indicadores"},
    )
    assert response.status_code == 201
    return response.json()


def _create_produto(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/cadastro/produtos-finais",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "PRD-IND-01",
            "descricao": "Produto Indicadores",
            "unidade_medida": "UN",
            "margem_lucro_padrao_pct": "20",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_insumo(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/cadastro/insumos",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "INS-IND-01",
            "descricao": "Insumo Indicadores",
            "categoria": "OUTRO",
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
            "codigo": "CT-IND-01",
            "nome": "Centro Indicadores",
            "tipo_maquina": "ROUTER_CNC",
            "taxa_horaria": "120.00",
            "setup_padrao_min": 10,
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

    add_item = client.post(
        f"/api/v1/engenharia-bom/boms/{bom_data['id']}/itens",
        headers=ADMIN_HEADERS,
        json={"item_tipo": "INSUMO", "insumo_id": insumo_id, "quantidade": "1"},
    )
    assert add_item.status_code == 201
    return bom_data


def _create_orcamento(
    client: TestClient,
    *,
    cliente_id: int,
    produto_id: int,
    bom_id: int,
    centro_id: int,
) -> dict:
    response = client.post(
        "/api/v1/orcamentos",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "ORC-IND-01",
            "cliente_id": cliente_id,
            "produto_final_id": produto_id,
            "bom_id": bom_id,
            "quantidade": "10",
            "margem_lucro_pct": "10",
            "operacoes": [
                {
                    "centro_trabalho_id": centro_id,
                    "setup_min": "10",
                    "ciclo_min": "2",
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_ordem(
    client: TestClient,
    *,
    cliente_id: int,
    produto_id: int,
    bom_id: int,
    centro_id: int,
) -> dict:
    response = client.post(
        "/api/v1/ordens-producao",
        headers=PCP_HEADERS,
        json={
            "cliente_id": cliente_id,
            "produto_final_id": produto_id,
            "bom_id": bom_id,
            "quantidade_planejada": "10",
            "operacoes": [
                {
                    "centro_trabalho_id": centro_id,
                    "setup_planejado_min": "10",
                    "ciclo_planejado_min": "2",
                }
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def _setup_cenario_indicadores(client: TestClient) -> dict:
    cliente = _create_cliente(client)
    produto = _create_produto(client)
    insumo = _create_insumo(client)
    centro = _create_centro(client)
    bom = _create_bom(client, produto_id=produto["id"], insumo_id=insumo["id"])
    _ = _create_orcamento(
        client,
        cliente_id=cliente["id"],
        produto_id=produto["id"],
        bom_id=bom["id"],
        centro_id=centro["id"],
    )
    ordem = _create_ordem(
        client,
        cliente_id=cliente["id"],
        produto_id=produto["id"],
        bom_id=bom["id"],
        centro_id=centro["id"],
    )

    lote = client.post(
        "/api/v1/estoque-retalhos/lotes",
        headers=ADMIN_HEADERS,
        json={
            "insumo_id": insumo["id"],
            "codigo_lote": "L-IND-001",
            "quantidade_inicial": "20",
            "custo_total": "200",
        },
    )
    assert lote.status_code == 201
    lote_data = lote.json()

    consumo = client.post(
        f"/api/v1/estoque-retalhos/lotes/{lote_data['id']}/consumos",
        headers=OPERADOR_HEADERS,
        json={"quantidade": "8", "ordem_id": ordem["id"]},
    )
    assert consumo.status_code == 200

    retalho = client.post(
        f"/api/v1/estoque-retalhos/lotes/{lote_data['id']}/retalhos",
        headers=OPERADOR_HEADERS,
        json={
            "codigo_lote_retalho": "RET-IND-001",
            "quantidade": "5",
            "ordem_id": ordem["id"],
        },
    )
    assert retalho.status_code == 200
    retalho_lote = retalho.json()["lote_retalho"]

    consumo_retalho = client.post(
        f"/api/v1/estoque-retalhos/lotes/{retalho_lote['id']}/consumos",
        headers=OPERADOR_HEADERS,
        json={"quantidade": "2", "ordem_id": ordem["id"]},
    )
    assert consumo_retalho.status_code == 200

    operacao_id = ordem["operacoes"][0]["id"]
    start = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={"evento": "START", "data_hora_evento": "2026-02-16T08:00:00Z"},
    )
    assert start.status_code == 201
    pausa = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={"evento": "PAUSA", "data_hora_evento": "2026-02-16T08:10:00Z"},
    )
    assert pausa.status_code == 201
    retomada = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={"evento": "RETOMADA", "data_hora_evento": "2026-02-16T08:15:00Z"},
    )
    assert retomada.status_code == 201
    stop = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={
            "evento": "STOP",
            "data_hora_evento": "2026-02-16T08:25:00Z",
            "quantidade_produzida": "8",
        },
    )
    assert stop.status_code == 201
    refugo = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/refugos",
        headers=OPERADOR_HEADERS,
        json={"quantidade": "2", "motivo": "Peça fora de medida"},
    )
    assert refugo.status_code == 201

    return {
        "ordem_id": ordem["id"],
        "numero_op": ordem["numero_op"],
        "lote_origem_id": lote_data["id"],
        "lote_retalho_id": retalho_lote["id"],
    }


def test_kpis_gerais_planejado_real_e_orcado(client: TestClient) -> None:
    contexto = _setup_cenario_indicadores(client)
    _ = contexto

    response = client.get("/api/v1/indicadores/kpis", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    body = response.json()

    assert body["total_ordens"] == 1
    assert float(body["quantidade_planejada_total"]) == 10.0
    assert float(body["quantidade_produzida_total"]) == 8.0
    assert float(body["quantidade_refugada_total"]) == 2.0
    assert float(body["refugo_pct"]) == pytest.approx(20.0)
    assert float(body["tempo_planejado_horas"]) == pytest.approx(0.5)
    assert float(body["tempo_real_horas"]) == pytest.approx(20 / 60)
    assert float(body["eficiencia_pct"]) == pytest.approx(150.0)
    assert float(body["custo_material_planejado"]) == pytest.approx(100.0)
    assert float(body["custo_material_real"]) == pytest.approx(100.0)
    assert float(body["custo_maquina_planejado"]) == pytest.approx(60.0)
    assert float(body["custo_maquina_real"]) == pytest.approx(40.0)
    assert float(body["custo_total_planejado"]) == pytest.approx(160.0)
    assert float(body["custo_total_real"]) == pytest.approx(140.0)
    assert float(body["custo_total_orcado"]) == pytest.approx(160.0)
    assert float(body["desvio_custo_real_vs_orcado"]) == pytest.approx(-20.0)


def test_indicadores_por_ordem_retorna_lista_com_metricas(client: TestClient) -> None:
    contexto = _setup_cenario_indicadores(client)

    response = client.get(
        f"/api/v1/indicadores/ordens?search={contexto['numero_op']}&status=FINALIZADA",
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["meta"]["total"] == 1
    item = body["items"][0]
    assert item["ordem_id"] == contexto["ordem_id"]
    assert item["status"] == "FINALIZADA"
    assert float(item["eficiencia_pct"]) == pytest.approx(150.0)
    assert float(item["custo_total_real"]) == pytest.approx(140.0)


def test_rastreabilidade_ordem_lote_consumo_e_retalho(client: TestClient) -> None:
    contexto = _setup_cenario_indicadores(client)

    response = client.get(
        f"/api/v1/indicadores/rastreabilidade/ordens/{contexto['ordem_id']}",
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["ordem_id"] == contexto["ordem_id"]
    assert len(body["operacoes"]) == 1
    tipos = {item["tipo_movimento"] for item in body["movimentacoes"]}
    assert {"CONSUMO_OP", "RETALHO_GERADO", "RETALHO_CONSUMIDO"}.issubset(tipos)

    lotes = {item["lote_id"] for item in body["lotes_relacionados"]}
    assert contexto["lote_origem_id"] in lotes
    assert contexto["lote_retalho_id"] in lotes

    assert any(
        fluxo["lote_origem_id"] == contexto["lote_origem_id"]
        and fluxo["lote_retalho_id"] == contexto["lote_retalho_id"]
        for fluxo in body["fluxo_retalhos"]
    )
