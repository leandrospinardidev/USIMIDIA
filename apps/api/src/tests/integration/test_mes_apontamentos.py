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
from modules.mes_apontamentos.infrastructure import models as mes_models  # noqa: F401
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


def _create_produto(client: TestClient, codigo: str) -> dict:
    response = client.post(
        "/api/v1/cadastro/produtos-finais",
        headers=ADMIN_HEADERS,
        json={"codigo": codigo, "descricao": "Produto MES", "unidade_medida": "UN"},
    )
    assert response.status_code == 201
    return response.json()


def _create_insumo(client: TestClient, codigo: str) -> dict:
    response = client.post(
        "/api/v1/cadastro/insumos",
        headers=ADMIN_HEADERS,
        json={
            "codigo": codigo,
            "descricao": "Insumo MES",
            "categoria": "OUTRO",
            "unidade_medida": "UN",
            "custo_unitario": "5.00",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_centro(client: TestClient, codigo: str) -> dict:
    response = client.post(
        "/api/v1/cadastro/centros-trabalho",
        headers=ADMIN_HEADERS,
        json={
            "codigo": codigo,
            "nome": "Centro MES",
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


def _create_op_with_one_operation(client: TestClient, suffix: str) -> tuple[int, int]:
    produto = _create_produto(client, f"PRD-MES-{suffix}")
    insumo = _create_insumo(client, f"INS-MES-{suffix}")
    centro = _create_centro(client, f"CT-MES-{suffix}")
    bom = _create_bom(client, produto_id=produto["id"], insumo_id=insumo["id"])

    create_op = client.post(
        "/api/v1/ordens-producao",
        headers=PCP_HEADERS,
        json={
            "produto_final_id": produto["id"],
            "bom_id": bom["id"],
            "quantidade_planejada": "10",
            "operacoes": [
                {
                    "centro_trabalho_id": centro["id"],
                    "setup_planejado_min": "10",
                    "ciclo_planejado_min": "2",
                }
            ],
        },
    )
    assert create_op.status_code == 201
    body = create_op.json()
    return body["id"], body["operacoes"][0]["id"]


def test_eventos_mes_atualizam_status_e_producao(client: TestClient) -> None:
    ordem_id, operacao_id = _create_op_with_one_operation(client, "01")

    start = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={"evento": "START", "data_hora_evento": "2026-02-16T10:00:00Z"},
    )
    assert start.status_code == 201
    assert start.json()["status_operacao"] == "EM_EXECUCAO"
    assert start.json()["status_ordem"] == "EM_PRODUCAO"

    pausa = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={"evento": "PAUSA", "data_hora_evento": "2026-02-16T10:30:00Z"},
    )
    assert pausa.status_code == 201
    assert pausa.json()["status_operacao"] == "PAUSADA"
    assert pausa.json()["status_ordem"] == "PAUSADA"

    retomada = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={"evento": "RETOMADA", "data_hora_evento": "2026-02-16T10:40:00Z"},
    )
    assert retomada.status_code == 201
    assert retomada.json()["status_operacao"] == "EM_EXECUCAO"

    stop = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={
            "evento": "STOP",
            "data_hora_evento": "2026-02-16T11:00:00Z",
            "quantidade_produzida": "5",
        },
    )
    assert stop.status_code == 201
    assert stop.json()["status_operacao"] == "CONCLUIDA"
    assert stop.json()["status_ordem"] == "FINALIZADA"

    ordem = client.get(f"/api/v1/ordens-producao/{ordem_id}", headers=PCP_HEADERS)
    assert ordem.status_code == 200
    assert ordem.json()["status"] == "FINALIZADA"
    assert float(ordem.json()["quantidade_produzida"]) == 5.0

    eventos = client.get(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
    )
    assert eventos.status_code == 200
    assert eventos.json()["meta"]["total"] == 4


def test_resumo_tempo_e_refugo(client: TestClient) -> None:
    ordem_id, operacao_id = _create_op_with_one_operation(client, "02")

    start = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={"evento": "START", "data_hora_evento": "2026-02-16T08:00:00Z"},
    )
    assert start.status_code == 201

    stop = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={
            "evento": "STOP",
            "data_hora_evento": "2026-02-16T08:20:00Z",
            "quantidade_produzida": "2",
        },
    )
    assert stop.status_code == 201

    refugo = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/refugos",
        headers=OPERADOR_HEADERS,
        json={"quantidade": "1", "motivo": "Trinca na usinagem"},
    )
    assert refugo.status_code == 201
    assert float(refugo.json()["quantidade_refugada_total_ordem"]) == 1.0

    resumo = client.get(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/resumo-tempo",
        headers=OPERADOR_HEADERS,
    )
    assert resumo.status_code == 200
    resumo_json = resumo.json()
    assert float(resumo_json["total_segundos"]) == pytest.approx(1200.0)
    assert float(resumo_json["total_horas"]) == pytest.approx(1200 / 3600)
    assert float(resumo_json["quantidade_produzida_total"]) == 2.0
    assert float(resumo_json["quantidade_refugada_total"]) == 1.0

    ordem = client.get(f"/api/v1/ordens-producao/{ordem_id}", headers=PCP_HEADERS)
    assert ordem.status_code == 200
    assert float(ordem.json()["quantidade_refugada"]) == 1.0

    refugos = client.get(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/refugos",
        headers=OPERADOR_HEADERS,
    )
    assert refugos.status_code == 200
    assert refugos.json()["meta"]["total"] == 1


def test_evento_invalido_para_status_operacao(client: TestClient) -> None:
    _, operacao_id = _create_op_with_one_operation(client, "03")

    pause_invalid = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={"evento": "PAUSA"},
    )
    assert pause_invalid.status_code == 409
    assert "invalido para operacao em status PENDENTE" in pause_invalid.json()["detail"]


def test_data_hora_evento_nao_pode_regredir(client: TestClient) -> None:
    _, operacao_id = _create_op_with_one_operation(client, "04")

    start = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={"evento": "START", "data_hora_evento": "2026-02-16T09:00:00Z"},
    )
    assert start.status_code == 201

    invalid_time = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=OPERADOR_HEADERS,
        json={"evento": "PAUSA", "data_hora_evento": "2026-02-16T08:59:00Z"},
    )
    assert invalid_time.status_code == 422
    assert "data_hora_evento nao pode ser menor" in invalid_time.json()["detail"]
