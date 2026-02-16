from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import UserRole, require_roles
from modules.mes_apontamentos.application.services import MesApontamentosService
from modules.mes_apontamentos.presentation.schemas import (
    ApontamentoCreate,
    ApontamentoListResponse,
    ApontamentoResponse,
    RefugoCreate,
    RefugoListResponse,
    RefugoResponse,
    ResumoTempoResponse,
)
from shared.application.pagination import PageMeta

router = APIRouter(prefix="/mes-apontamentos", tags=["MES Apontamentos"])

ReadPermission = Annotated[
    UserRole,
    Depends(require_roles(UserRole.ADMIN, UserRole.PCP, UserRole.OPERADOR)),
]
WritePermission = Annotated[
    UserRole,
    Depends(require_roles(UserRole.ADMIN, UserRole.PCP, UserRole.OPERADOR)),
]
DbSession = Annotated[Session, Depends(get_db)]


def _service(db: Session) -> MesApontamentosService:
    return MesApontamentosService(db)


def _paginated_response(
    items: list[Any], *, page: int, page_size: int, total: int
) -> dict[str, Any]:
    return {"items": items, "meta": PageMeta(page=page, page_size=page_size, total=total)}


@router.get("/ping")
def ping_mes() -> dict[str, str]:
    return {"module": "mes_apontamentos", "status": "ok"}


@router.post(
    "/operacoes/{ordem_operacao_id}/eventos",
    response_model=ApontamentoResponse,
    status_code=status.HTTP_201_CREATED,
)
def registrar_evento(
    _: WritePermission,
    db: DbSession,
    ordem_operacao_id: int,
    payload: ApontamentoCreate,
):
    return _service(db).registrar_evento(
        ordem_operacao_id=ordem_operacao_id,
        payload=payload.model_dump(exclude_unset=True),
    )


@router.get("/operacoes/{ordem_operacao_id}/eventos", response_model=ApontamentoListResponse)
def list_eventos(
    _: ReadPermission,
    db: DbSession,
    ordem_operacao_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    items, total = _service(db).list_eventos(
        ordem_operacao_id=ordem_operacao_id,
        page=page,
        page_size=page_size,
    )
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.post(
    "/operacoes/{ordem_operacao_id}/refugos",
    response_model=RefugoResponse,
    status_code=status.HTTP_201_CREATED,
)
def registrar_refugo(
    _: WritePermission,
    db: DbSession,
    ordem_operacao_id: int,
    payload: RefugoCreate,
):
    return _service(db).registrar_refugo(
        ordem_operacao_id=ordem_operacao_id,
        payload=payload.model_dump(exclude_unset=True),
    )


@router.get("/operacoes/{ordem_operacao_id}/refugos", response_model=RefugoListResponse)
def list_refugos(
    _: ReadPermission,
    db: DbSession,
    ordem_operacao_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    items, total = _service(db).list_refugos(
        ordem_operacao_id=ordem_operacao_id,
        page=page,
        page_size=page_size,
    )
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.get(
    "/operacoes/{ordem_operacao_id}/resumo-tempo",
    response_model=ResumoTempoResponse,
)
def resumo_tempo_operacao(
    _: ReadPermission,
    db: DbSession,
    ordem_operacao_id: int,
):
    return _service(db).resumo_tempo_operacao(ordem_operacao_id=ordem_operacao_id)
