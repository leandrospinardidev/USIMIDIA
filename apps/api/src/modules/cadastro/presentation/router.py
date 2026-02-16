from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import UserRole, require_roles
from modules.cadastro.application.services import CrudService
from modules.cadastro.infrastructure.models import (
    CentroTrabalhoModel,
    ClienteModel,
    InsumoModel,
    ProdutoFinalModel,
)
from modules.cadastro.presentation.schemas import (
    CentroTrabalhoCreate,
    CentroTrabalhoListResponse,
    CentroTrabalhoResponse,
    CentroTrabalhoUpdate,
    ClienteCreate,
    ClienteListResponse,
    ClienteResponse,
    ClienteUpdate,
    InsumoCreate,
    InsumoListResponse,
    InsumoResponse,
    InsumoUpdate,
    ProdutoFinalCreate,
    ProdutoFinalListResponse,
    ProdutoFinalResponse,
    ProdutoFinalUpdate,
)
from shared.application.pagination import PageMeta

router = APIRouter(prefix="/cadastro", tags=["Cadastro"])

ReadPermission = Annotated[
    UserRole,
    Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.PCP,
            UserRole.COMPRAS,
            UserRole.OPERADOR,
        )
    ),
]
WritePermission = Annotated[
    UserRole,
    Depends(require_roles(UserRole.ADMIN, UserRole.PCP, UserRole.COMPRAS)),
]
DbSession = Annotated[Session, Depends(get_db)]


def _get_cliente_service(db: Session) -> CrudService[ClienteModel]:
    return CrudService(
        db=db,
        model=ClienteModel,
        resource_name="cliente",
        search_fields=[
            ClienteModel.codigo,
            ClienteModel.razao_social,
            ClienteModel.nome_fantasia,
        ],
    )


def _get_insumo_service(db: Session) -> CrudService[InsumoModel]:
    return CrudService(
        db=db,
        model=InsumoModel,
        resource_name="insumo",
        search_fields=[InsumoModel.codigo, InsumoModel.descricao],
    )


def _get_centro_service(db: Session) -> CrudService[CentroTrabalhoModel]:
    return CrudService(
        db=db,
        model=CentroTrabalhoModel,
        resource_name="centro de trabalho",
        search_fields=[
            CentroTrabalhoModel.codigo,
            CentroTrabalhoModel.nome,
            CentroTrabalhoModel.tipo_maquina,
        ],
    )


def _get_produto_service(db: Session) -> CrudService[ProdutoFinalModel]:
    return CrudService(
        db=db,
        model=ProdutoFinalModel,
        resource_name="produto final",
        search_fields=[
            ProdutoFinalModel.codigo,
            ProdutoFinalModel.descricao,
            ProdutoFinalModel.revisao_atual,
        ],
    )


def _paginated_response(
    items: list[Any], *, page: int, page_size: int, total: int
) -> dict[str, Any]:
    return {
        "items": items,
        "meta": PageMeta(page=page, page_size=page_size, total=total),
    }


@router.get("/ping")
def ping_cadastro() -> dict[str, str]:
    return {"module": "cadastro", "status": "ok"}


@router.get("/admin-check")
def admin_check(
    _: Annotated[UserRole, Depends(require_roles(UserRole.ADMIN, UserRole.PCP))],
) -> dict[str, str]:
    return {"access": "granted"}


@router.post("/clientes", response_model=ClienteResponse, status_code=status.HTTP_201_CREATED)
def create_cliente(
    _: WritePermission,
    db: DbSession,
    payload: ClienteCreate,
) -> ClienteModel:
    service = _get_cliente_service(db)
    return service.create(payload.model_dump())


@router.get("/clientes", response_model=ClienteListResponse)
def list_clientes(
    _: ReadPermission,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None, max_length=100),
    ativo: bool | None = Query(default=None),
) -> dict[str, Any]:
    service = _get_cliente_service(db)
    items, total = service.list(page=page, page_size=page_size, search=search, ativo=ativo)
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.get("/clientes/{cliente_id}", response_model=ClienteResponse)
def get_cliente(_: ReadPermission, db: DbSession, cliente_id: int) -> ClienteModel:
    service = _get_cliente_service(db)
    return service.get_or_404(cliente_id)


@router.patch("/clientes/{cliente_id}", response_model=ClienteResponse)
def update_cliente(
    _: WritePermission,
    db: DbSession,
    cliente_id: int,
    payload: ClienteUpdate,
) -> ClienteModel:
    service = _get_cliente_service(db)
    return service.update(cliente_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/clientes/{cliente_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_cliente(_: WritePermission, db: DbSession, cliente_id: int) -> Response:
    service = _get_cliente_service(db)
    service.soft_delete(cliente_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/insumos", response_model=InsumoResponse, status_code=status.HTTP_201_CREATED)
def create_insumo(
    _: WritePermission,
    db: DbSession,
    payload: InsumoCreate,
) -> InsumoModel:
    service = _get_insumo_service(db)
    return service.create(payload.model_dump())


@router.get("/insumos", response_model=InsumoListResponse)
def list_insumos(
    _: ReadPermission,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None, max_length=100),
    ativo: bool | None = Query(default=None),
) -> dict[str, Any]:
    service = _get_insumo_service(db)
    items, total = service.list(page=page, page_size=page_size, search=search, ativo=ativo)
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.get("/insumos/{insumo_id}", response_model=InsumoResponse)
def get_insumo(_: ReadPermission, db: DbSession, insumo_id: int) -> InsumoModel:
    service = _get_insumo_service(db)
    return service.get_or_404(insumo_id)


@router.patch("/insumos/{insumo_id}", response_model=InsumoResponse)
def update_insumo(
    _: WritePermission,
    db: DbSession,
    insumo_id: int,
    payload: InsumoUpdate,
) -> InsumoModel:
    service = _get_insumo_service(db)
    return service.update(insumo_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/insumos/{insumo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_insumo(_: WritePermission, db: DbSession, insumo_id: int) -> Response:
    service = _get_insumo_service(db)
    service.soft_delete(insumo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/centros-trabalho",
    response_model=CentroTrabalhoResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_centro_trabalho(
    _: WritePermission,
    db: DbSession,
    payload: CentroTrabalhoCreate,
) -> CentroTrabalhoModel:
    service = _get_centro_service(db)
    return service.create(payload.model_dump())


@router.get("/centros-trabalho", response_model=CentroTrabalhoListResponse)
def list_centros_trabalho(
    _: ReadPermission,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None, max_length=100),
    ativo: bool | None = Query(default=None),
) -> dict[str, Any]:
    service = _get_centro_service(db)
    items, total = service.list(page=page, page_size=page_size, search=search, ativo=ativo)
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.get(
    "/centros-trabalho/{centro_id}",
    response_model=CentroTrabalhoResponse,
)
def get_centro_trabalho(_: ReadPermission, db: DbSession, centro_id: int) -> CentroTrabalhoModel:
    service = _get_centro_service(db)
    return service.get_or_404(centro_id)


@router.patch("/centros-trabalho/{centro_id}", response_model=CentroTrabalhoResponse)
def update_centro_trabalho(
    _: WritePermission,
    db: DbSession,
    centro_id: int,
    payload: CentroTrabalhoUpdate,
) -> CentroTrabalhoModel:
    service = _get_centro_service(db)
    return service.update(centro_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/centros-trabalho/{centro_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_centro_trabalho(_: WritePermission, db: DbSession, centro_id: int) -> Response:
    service = _get_centro_service(db)
    service.soft_delete(centro_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/produtos-finais",
    response_model=ProdutoFinalResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_produto_final(
    _: WritePermission,
    db: DbSession,
    payload: ProdutoFinalCreate,
) -> ProdutoFinalModel:
    service = _get_produto_service(db)
    return service.create(payload.model_dump())


@router.get("/produtos-finais", response_model=ProdutoFinalListResponse)
def list_produtos_finais(
    _: ReadPermission,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None, max_length=100),
    ativo: bool | None = Query(default=None),
) -> dict[str, Any]:
    service = _get_produto_service(db)
    items, total = service.list(page=page, page_size=page_size, search=search, ativo=ativo)
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.get(
    "/produtos-finais/{produto_id}",
    response_model=ProdutoFinalResponse,
)
def get_produto_final(_: ReadPermission, db: DbSession, produto_id: int) -> ProdutoFinalModel:
    service = _get_produto_service(db)
    return service.get_or_404(produto_id)


@router.patch("/produtos-finais/{produto_id}", response_model=ProdutoFinalResponse)
def update_produto_final(
    _: WritePermission,
    db: DbSession,
    produto_id: int,
    payload: ProdutoFinalUpdate,
) -> ProdutoFinalModel:
    service = _get_produto_service(db)
    return service.update(produto_id, payload.model_dump(exclude_unset=True))


@router.delete(
    "/produtos-finais/{produto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_produto_final(_: WritePermission, db: DbSession, produto_id: int) -> Response:
    service = _get_produto_service(db)
    service.soft_delete(produto_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
