from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.config import get_settings
from core.database import Base, get_db
from main import app
from modules.cadastro.infrastructure import models as cadastro_models  # noqa: F401
from modules.engenharia_bom.infrastructure import models as bom_models  # noqa: F401
from modules.orcamentos.application.services import OrcamentosService
from modules.orcamentos.infrastructure import models as orc_models  # noqa: F401

ADMIN_HEADERS = {"X-User-Role": "admin"}


@pytest.fixture
def client(tmp_path) -> TestClient:
    os.environ["UPLOADS_DIR"] = str(tmp_path / "uploads")
    get_settings.cache_clear()
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
    get_settings.cache_clear()


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


def _create_ordem_finalizada_com_mes(
    client: TestClient,
    *,
    produto_id: int,
    bom_id: int,
    centro_id: int,
) -> dict:
    create_ordem = client.post(
        "/api/v1/ordens-producao",
        headers=ADMIN_HEADERS,
        json={
            "produto_final_id": produto_id,
            "bom_id": bom_id,
            "quantidade_planejada": "2",
            "operacoes": [
                {
                    "centro_trabalho_id": centro_id,
                    "setup_planejado_min": "10",
                    "ciclo_planejado_min": "6",
                }
            ],
        },
    )
    assert create_ordem.status_code == 201
    ordem = create_ordem.json()
    operacao_id = ordem["operacoes"][0]["id"]

    evento_start = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=ADMIN_HEADERS,
        json={"evento": "START", "data_hora_evento": "2026-02-16T08:00:00Z"},
    )
    assert evento_start.status_code == 201
    evento_stop = client.post(
        f"/api/v1/mes-apontamentos/operacoes/{operacao_id}/eventos",
        headers=ADMIN_HEADERS,
        json={
            "evento": "STOP",
            "data_hora_evento": "2026-02-16T08:26:00Z",
            "quantidade_produzida": "2",
        },
    )
    assert evento_stop.status_code == 201
    return ordem


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
            "referencia_projeto": "PROJ-ALPHA-001",
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
    assert orc["referencia_projeto"] == "PROJ-ALPHA-001"
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
    assert listagem.json()["items"][0]["referencia_projeto"] == "PROJ-ALPHA-001"

    status_update = client.patch(
        f"/api/v1/orcamentos/{orc['id']}/status",
        headers=ADMIN_HEADERS,
        json={"status": "ENVIADO"},
    )
    assert status_update.status_code == 200
    assert status_update.json()["status"] == "ENVIADO"


def test_upload_listagem_e_download_de_anexos_orcamento(client: TestClient) -> None:
    cliente = _create_cliente(client)
    produto = _create_produto(client)
    insumo = _create_insumo(client)
    centro = _create_centro(client)
    bom = _create_bom_base(client, produto_id=produto["id"], insumo_id=insumo["id"])

    create_orc = client.post(
        "/api/v1/orcamentos",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "ORC-TEST-ANX-001",
            "referencia_projeto": "PROJ-ANEXO-001",
            "cliente_id": cliente["id"],
            "produto_final_id": produto["id"],
            "bom_id": bom["id"],
            "quantidade": "1",
            "margem_lucro_pct": "20",
            "operacoes": [
                {
                    "centro_trabalho_id": centro["id"],
                    "setup_min": "10",
                    "ciclo_min": "5",
                }
            ],
        },
    )
    assert create_orc.status_code == 201
    orc = create_orc.json()

    dxf_content = b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n"
    upload = client.post(
        f"/api/v1/orcamentos/{orc['id']}/anexos",
        headers=ADMIN_HEADERS,
        files={"file": ("desenho_tecnico.dxf", dxf_content, "application/dxf")},
        data={"observacao": "Primeira versao do desenho"},
    )
    assert upload.status_code == 201
    anexo = upload.json()
    assert anexo["orcamento_id"] == orc["id"]
    assert anexo["nome_arquivo_original"] == "desenho_tecnico.dxf"
    assert anexo["tamanho_bytes"] == len(dxf_content)
    assert anexo["download_path"].endswith(f"/orcamentos/anexos/{anexo['id']}/download")

    list_anexos = client.get(
        f"/api/v1/orcamentos/{orc['id']}/anexos?page=1&page_size=20",
        headers=ADMIN_HEADERS,
    )
    assert list_anexos.status_code == 200
    payload = list_anexos.json()
    assert payload["meta"]["total"] == 1
    assert payload["items"][0]["id"] == anexo["id"]

    detail = client.get(f"/api/v1/orcamentos/{orc['id']}", headers=ADMIN_HEADERS)
    assert detail.status_code == 200
    assert len(detail.json()["anexos"]) == 1

    download = client.get(
        f"/api/v1/orcamentos/anexos/{anexo['id']}/download",
        headers=ADMIN_HEADERS,
    )
    assert download.status_code == 200
    assert download.content == dxf_content


def test_simulacao_automatica_por_pdf(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    centro = _create_centro(client)

    def _fake_extract_pdf_text(self: OrcamentosService, _: bytes) -> str:
        _ = self
        return "AÇO CARBONO QTD: 2 DIÂMETRO 39 H7 DIÂMETRO 16 H7"

    monkeypatch.setattr(OrcamentosService, "_extract_pdf_text", _fake_extract_pdf_text)

    response = client.post(
        "/api/v1/orcamentos/simulacoes/pdf",
        headers=ADMIN_HEADERS,
        files={"file": ("desenho.pdf", b"%PDF-1.4 qualquer", "application/pdf")},
        data={
            "centro_trabalho_id": str(centro["id"]),
            "margem_lucro_pct": "20",
            "custo_indireto_pct": "5",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["leitura"]["material_inferido"] == "ACO CARBONO"
    assert body["leitura"]["quantidade_considerada"] == 2
    assert len(body["leitura"]["diametros_mm"]) >= 2
    assert float(body["custos"]["preco_venda_sugerido"]) > 0

    invalid = client.post(
        "/api/v1/orcamentos/simulacoes/pdf",
        headers=ADMIN_HEADERS,
        files={"file": ("desenho.dxf", b"0\nSECTION", "text/plain")},
        data={"centro_trabalho_id": str(centro["id"])},
    )
    assert invalid.status_code == 422


def test_presets_cnc_crud_e_recalibracao_mes(client: TestClient) -> None:
    cliente = _create_cliente(client)
    produto = _create_produto(client)
    insumo = _create_insumo(client)
    centro = _create_centro(client)
    bom = _create_bom_base(client, produto_id=produto["id"], insumo_id=insumo["id"])
    _create_ordem_finalizada_com_mes(
        client,
        produto_id=produto["id"],
        bom_id=bom["id"],
        centro_id=centro["id"],
    )

    create_preset = client.post(
        "/api/v1/orcamentos/presets-cnc",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "PRCNC-TEST-001",
            "nome": "Preset Flange Aco",
            "cliente_id": cliente["id"],
            "produto_final_id": produto["id"],
            "centro_trabalho_id": centro["id"],
            "fabricante_referencia": "Haas",
            "perfil_maquina": "VF-2",
            "familia_peca": "Flange circular furada",
            "tipo_peca": "FLANGE",
            "material_referencia": "Aco carbono",
            "operacao_principal": "Desbaste",
            "diametro_referencia_mm": "120",
            "comprimento_referencia_mm": "25",
            "fator_ciclo": "1.00",
            "fator_setup": "1.00",
            "margem_lucro_pct": "24",
            "custo_indireto_pct": "7",
            "operacoes_template": [
                {
                    "sequencia": 1,
                    "centro_trabalho_id": centro["id"],
                    "setup_min": "10",
                    "ciclo_min": "6",
                    "descricao": "Desbaste flange",
                }
            ],
        },
    )
    assert create_preset.status_code == 201
    preset = create_preset.json()
    assert preset["codigo"] == "PRCNC-TEST-001"
    assert preset["cliente_id"] == cliente["id"]

    list_presets = client.get(
        f"/api/v1/orcamentos/presets-cnc?cliente_id={cliente['id']}&produto_final_id={produto['id']}",
        headers=ADMIN_HEADERS,
    )
    assert list_presets.status_code == 200
    assert list_presets.json()["meta"]["total"] >= 1

    update_preset = client.patch(
        f"/api/v1/orcamentos/presets-cnc/{preset['id']}",
        headers=ADMIN_HEADERS,
        json={"nome": "Preset Flange Aco v2", "fator_ciclo": "1.10"},
    )
    assert update_preset.status_code == 200
    assert update_preset.json()["nome"] == "Preset Flange Aco v2"

    recalibrar = client.post(
        f"/api/v1/orcamentos/presets-cnc/{preset['id']}/recalibrar-mes",
        headers=ADMIN_HEADERS,
        json={
            "janela_dias": 365,
            "centro_trabalho_id": centro["id"],
            "produto_final_id": produto["id"],
            "suavizacao_alpha": "0.80",
        },
    )
    assert recalibrar.status_code == 200
    recal_payload = recalibrar.json()
    assert recal_payload["amostras_utilizadas"] >= 1
    assert float(recal_payload["tempo_real_min_total"]) > 0
