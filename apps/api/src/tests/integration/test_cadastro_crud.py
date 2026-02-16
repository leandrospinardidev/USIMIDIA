from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from main import app
from modules.cadastro.infrastructure import models  # noqa: F401

ADMIN_HEADERS = {"X-User-Role": "admin"}
OPERADOR_HEADERS = {"X-User-Role": "operador"}


@pytest.fixture
def client() -> TestClient:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_clientes_crud_com_inativacao(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/cadastro/clientes",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "CLI-001",
            "razao_social": "Metalurgica Alpha LTDA",
            "nome_fantasia": "Alpha",
            "cnpj_cpf": "12345678000199",
        },
    )
    assert create_response.status_code == 201
    cliente = create_response.json()
    assert cliente["codigo"] == "CLI-001"
    assert cliente["ativo"] is True

    duplicate_response = client.post(
        "/api/v1/cadastro/clientes",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "CLI-001",
            "razao_social": "Cliente Duplicado",
        },
    )
    assert duplicate_response.status_code == 409
    assert "Codigo ja cadastrado" in duplicate_response.json()["detail"]

    update_response = client.patch(
        f"/api/v1/cadastro/clientes/{cliente['id']}",
        headers=ADMIN_HEADERS,
        json={"nome_fantasia": "Alpha Atualizada"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["nome_fantasia"] == "Alpha Atualizada"

    delete_response = client.delete(
        f"/api/v1/cadastro/clientes/{cliente['id']}",
        headers=ADMIN_HEADERS,
    )
    assert delete_response.status_code == 204

    get_response = client.get(
        f"/api/v1/cadastro/clientes/{cliente['id']}",
        headers=ADMIN_HEADERS,
    )
    assert get_response.status_code == 200
    assert get_response.json()["ativo"] is False


def test_insumos_validacao_enum_e_permissoes(client: TestClient) -> None:
    forbidden_response = client.post(
        "/api/v1/cadastro/insumos",
        headers=OPERADOR_HEADERS,
        json={
            "codigo": "INS-001",
            "descricao": "Chapa Aco 2mm",
            "categoria": "CHAPA",
            "unidade_medida": "M2",
        },
    )
    assert forbidden_response.status_code == 403

    invalid_enum_response = client.post(
        "/api/v1/cadastro/insumos",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "INS-001",
            "descricao": "Chapa Aco 2mm",
            "categoria": "CHAPA",
            "unidade_medida": "INVALIDA",
        },
    )
    assert invalid_enum_response.status_code == 422

    create_response = client.post(
        "/api/v1/cadastro/insumos",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "INS-001",
            "descricao": "Chapa Aco 2mm",
            "categoria": "CHAPA",
            "unidade_medida": "M2",
            "custo_unitario": "120.50",
            "largura_mm": "2000",
            "altura_mm": "1000",
        },
    )
    assert create_response.status_code == 201
    insumo = create_response.json()
    assert insumo["codigo"] == "INS-001"

    read_response = client.get("/api/v1/cadastro/insumos", headers=OPERADOR_HEADERS)
    assert read_response.status_code == 200
    assert read_response.json()["meta"]["total"] == 1


def test_centros_de_trabalho_crud(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/cadastro/centros-trabalho",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "CT-ROUTER-01",
            "nome": "Router CNC 01",
            "tipo_maquina": "ROUTER_CNC",
            "taxa_horaria": "180.00",
            "setup_padrao_min": 15,
            "capacidade_horas_dia": "8",
        },
    )
    assert create_response.status_code == 201
    centro = create_response.json()

    duplicate_response = client.post(
        "/api/v1/cadastro/centros-trabalho",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "CT-ROUTER-01",
            "nome": "Router CNC Duplicado",
            "tipo_maquina": "ROUTER_CNC",
            "taxa_horaria": "190.00",
        },
    )
    assert duplicate_response.status_code == 409

    list_response = client.get(
        "/api/v1/cadastro/centros-trabalho?search=Router",
        headers=ADMIN_HEADERS,
    )
    assert list_response.status_code == 200
    assert list_response.json()["meta"]["total"] == 1

    update_response = client.patch(
        f"/api/v1/cadastro/centros-trabalho/{centro['id']}",
        headers=ADMIN_HEADERS,
        json={"taxa_horaria": "200.00"},
    )
    assert update_response.status_code == 200
    assert float(update_response.json()["taxa_horaria"]) == 200.0


def test_produtos_finais_crud(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/cadastro/produtos-finais",
        headers=ADMIN_HEADERS,
        json={
            "codigo": "PRD-0001",
            "descricao": "Maquina Laser Compacta",
            "revisao_atual": "A",
            "unidade_medida": "UN",
            "margem_lucro_padrao_pct": "35.00",
        },
    )
    assert create_response.status_code == 201
    produto = create_response.json()
    assert produto["codigo"] == "PRD-0001"

    list_response = client.get(
        "/api/v1/cadastro/produtos-finais?search=Laser",
        headers=ADMIN_HEADERS,
    )
    assert list_response.status_code == 200
    assert list_response.json()["meta"]["total"] == 1

    delete_response = client.delete(
        f"/api/v1/cadastro/produtos-finais/{produto['id']}",
        headers=ADMIN_HEADERS,
    )
    assert delete_response.status_code == 204

    inativos_response = client.get(
        "/api/v1/cadastro/produtos-finais?ativo=false",
        headers=ADMIN_HEADERS,
    )
    assert inativos_response.status_code == 200
    assert inativos_response.json()["meta"]["total"] == 1
