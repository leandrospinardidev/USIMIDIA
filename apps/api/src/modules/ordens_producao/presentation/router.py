from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import UserRole, require_roles
from modules.ordens_producao.application.services import OrdensProducaoService
from modules.ordens_producao.presentation.schemas import (
    OrdemListResponse,
    OrdemProducaoCreate,
    OrdemProducaoResponse,
    OrdemStatus,
    OrdemStatusUpdate,
    OrdemOperacaoCreate,
)
from shared.application.pagination import PageMeta

router = APIRouter(prefix="/ordens-producao", tags=["Ordens de Producao"])

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
    Depends(require_roles(UserRole.ADMIN, UserRole.PCP)),
]
DbSession = Annotated[Session, Depends(get_db)]


def _service(db: Session) -> OrdensProducaoService:
    return OrdensProducaoService(db)


def _paginated_response(
    items: list[Any], *, page: int, page_size: int, total: int
) -> dict[str, Any]:
    return {"items": items, "meta": PageMeta(page=page, page_size=page_size, total=total)}


@router.get("/ping")
def ping_ordens() -> dict[str, str]:
    return {"module": "ordens_producao", "status": "ok"}


@router.post("", response_model=OrdemProducaoResponse, status_code=status.HTTP_201_CREATED)
def create_ordem(_: WritePermission, db: DbSession, payload: OrdemProducaoCreate):
    return _service(db).create_ordem(payload.model_dump(exclude_unset=True))


@router.get("", response_model=OrdemListResponse)
def list_ordens(
    _: ReadPermission,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None, max_length=100),
    status_filter: Annotated[OrdemStatus | None, Query(alias="status")] = None,
) -> dict[str, Any]:
    items, total = _service(db).list_ordens(
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status_filter.value if status_filter else None,
    )
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.get("/{ordem_id}", response_model=OrdemProducaoResponse)
def get_ordem(_: ReadPermission, db: DbSession, ordem_id: int):
    return _service(db).get_ordem_detail(ordem_id)


@router.post("/{ordem_id}/operacoes", response_model=OrdemProducaoResponse)
def add_operacao(
    _: WritePermission,
    db: DbSession,
    ordem_id: int,
    payload: OrdemOperacaoCreate,
):
    return _service(db).add_operacao(ordem_id=ordem_id, payload=payload.model_dump(exclude_unset=True))


@router.patch("/{ordem_id}/status", response_model=OrdemProducaoResponse)
def update_status(
    _: WritePermission,
    db: DbSession,
    ordem_id: int,
    payload: OrdemStatusUpdate,
):
    return _service(db).update_status(ordem_id=ordem_id, new_status=payload.status)
