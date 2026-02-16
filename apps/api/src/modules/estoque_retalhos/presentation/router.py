from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import UserRole, require_roles
from modules.estoque_retalhos.application.services import EstoqueRetalhosService
from modules.estoque_retalhos.presentation.schemas import (
    AjusteLoteCreate,
    GerarRetalhoCreate,
    GerarRetalhoResponse,
    LoteConsumoCreate,
    LoteEntradaCreate,
    LoteListResponse,
    LoteResponse,
    MovimentacaoListResponse,
    MovimentoTipo,
    SaldoInsumoResponse,
)
from shared.application.pagination import PageMeta

router = APIRouter(prefix="/estoque-retalhos", tags=["Estoque e Retalhos"])

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
WriteEntradaPermission = Annotated[
    UserRole,
    Depends(require_roles(UserRole.ADMIN, UserRole.PCP, UserRole.COMPRAS)),
]
WriteProducaoPermission = Annotated[
    UserRole,
    Depends(require_roles(UserRole.ADMIN, UserRole.PCP, UserRole.OPERADOR)),
]
DbSession = Annotated[Session, Depends(get_db)]


def _service(db: Session) -> EstoqueRetalhosService:
    return EstoqueRetalhosService(db)


def _paginated_response(
    items: list[Any], *, page: int, page_size: int, total: int
) -> dict[str, Any]:
    return {"items": items, "meta": PageMeta(page=page, page_size=page_size, total=total)}


@router.get("/ping")
def ping_estoque() -> dict[str, str]:
    return {"module": "estoque_retalhos", "status": "ok"}


@router.post("/lotes", response_model=LoteResponse, status_code=status.HTTP_201_CREATED)
def create_lote(_: WriteEntradaPermission, db: DbSession, payload: LoteEntradaCreate):
    return _service(db).create_lote_entrada(payload.model_dump())


@router.get("/lotes", response_model=LoteListResponse)
def list_lotes(
    _: ReadPermission,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    insumo_id: int | None = Query(default=None, gt=0),
    com_saldo: bool | None = None,
    is_retalho: bool | None = None,
    search: str | None = Query(default=None, max_length=100),
) -> dict[str, Any]:
    items, total = _service(db).list_lotes(
        page=page,
        page_size=page_size,
        insumo_id=insumo_id,
        com_saldo=com_saldo,
        is_retalho=is_retalho,
        search=search,
    )
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.get("/lotes/{lote_id}", response_model=LoteResponse)
def get_lote(_: ReadPermission, db: DbSession, lote_id: int):
    return _service(db).get_lote_detail(lote_id)


@router.post("/lotes/{lote_id}/consumos", response_model=LoteResponse)
def consumir_lote(
    _: WriteProducaoPermission,
    db: DbSession,
    lote_id: int,
    payload: LoteConsumoCreate,
):
    return _service(db).consumir_lote(
        lote_id=lote_id,
        payload=payload.model_dump(exclude_unset=True),
    )


@router.post("/lotes/{lote_id}/retalhos", response_model=GerarRetalhoResponse)
def gerar_retalho(
    _: WriteProducaoPermission,
    db: DbSession,
    lote_id: int,
    payload: GerarRetalhoCreate,
):
    return _service(db).gerar_retalho(
        lote_id=lote_id,
        payload=payload.model_dump(exclude_unset=True),
    )


@router.post("/lotes/{lote_id}/ajustes", response_model=LoteResponse)
def ajustar_lote(
    _: WriteEntradaPermission,
    db: DbSession,
    lote_id: int,
    payload: AjusteLoteCreate,
):
    return _service(db).ajustar_lote(
        lote_id=lote_id,
        payload=payload.model_dump(exclude_unset=True),
    )


@router.get("/lotes/{lote_id}/movimentacoes", response_model=MovimentacaoListResponse)
def list_movimentacoes(
    _: ReadPermission,
    db: DbSession,
    lote_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    tipo_movimento: Annotated[MovimentoTipo | None, Query(alias="tipo")] = None,
) -> dict[str, Any]:
    items, total = _service(db).list_movimentacoes(
        lote_id=lote_id,
        page=page,
        page_size=page_size,
        tipo_movimento=tipo_movimento.value if tipo_movimento is not None else None,
    )
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.get("/saldos/insumos", response_model=list[SaldoInsumoResponse])
def saldos_insumos(
    _: ReadPermission,
    db: DbSession,
    only_positive: bool = Query(default=True),
):
    return _service(db).saldos_por_insumo(only_positive=only_positive)
