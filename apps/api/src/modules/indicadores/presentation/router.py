from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import UserRole, require_roles
from modules.indicadores.application.services import IndicadoresService
from modules.indicadores.presentation.schemas import (
    IndicadoresOrdemListResponse,
    KpisGeraisResponse,
    RastreabilidadeOrdemResponse,
)
from modules.ordens_producao.presentation.schemas import OrdemStatus
from shared.application.pagination import PageMeta

router = APIRouter(prefix="/indicadores", tags=["Indicadores"])

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
DbSession = Annotated[Session, Depends(get_db)]


def _service(db: Session) -> IndicadoresService:
    return IndicadoresService(db)


def _paginated_response(
    items: list[Any], *, page: int, page_size: int, total: int
) -> dict[str, Any]:
    return {"items": items, "meta": PageMeta(page=page, page_size=page_size, total=total)}


@router.get("/ping")
def ping_indicadores() -> dict[str, str]:
    return {"module": "indicadores", "status": "ok"}


@router.get("/kpis", response_model=KpisGeraisResponse)
def kpis_gerais(
    _: ReadPermission,
    db: DbSession,
    periodo_inicio: date | None = None,
    periodo_fim: date | None = None,
    centro_trabalho_id: int | None = Query(default=None, gt=0),
    ordem_id: int | None = Query(default=None, gt=0),
    status_filter: Annotated[OrdemStatus | None, Query(alias="status")] = None,
):
    return _service(db).kpis_gerais(
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        centro_trabalho_id=centro_trabalho_id,
        ordem_id=ordem_id,
        status_filter=status_filter.value if status_filter is not None else None,
    )


@router.get("/ordens", response_model=IndicadoresOrdemListResponse)
def indicadores_por_ordem(
    _: ReadPermission,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    periodo_inicio: date | None = None,
    periodo_fim: date | None = None,
    centro_trabalho_id: int | None = Query(default=None, gt=0),
    status_filter: Annotated[OrdemStatus | None, Query(alias="status")] = None,
    search: str | None = Query(default=None, max_length=100),
) -> dict[str, Any]:
    items, total = _service(db).indicadores_por_ordem(
        page=page,
        page_size=page_size,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        centro_trabalho_id=centro_trabalho_id,
        status_filter=status_filter.value if status_filter is not None else None,
        search=search,
    )
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.get(
    "/rastreabilidade/ordens/{ordem_id}",
    response_model=RastreabilidadeOrdemResponse,
)
def rastreabilidade_ordem(_: ReadPermission, db: DbSession, ordem_id: int):
    return _service(db).rastreabilidade_ordem(ordem_id)
