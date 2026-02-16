from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import UserRole, require_roles
from modules.engenharia_bom.application.services import BomService
from modules.engenharia_bom.presentation.schemas import (
    BomCreate,
    BomExplosionResponse,
    BomItemCreate,
    BomItemResponse,
    BomItemUpdate,
    BomListResponse,
    BomResponse,
    BomStatus,
    BomTreeResponse,
    BomUpdate,
)
from shared.application.pagination import PageMeta

router = APIRouter(prefix="/engenharia-bom", tags=["Engenharia BOM"])

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


def _service(db: Session) -> BomService:
    return BomService(db)


def _paginated_response(items: list[Any], *, page: int, page_size: int, total: int) -> dict[str, Any]:
    return {"items": items, "meta": PageMeta(page=page, page_size=page_size, total=total)}


@router.get("/ping")
def ping_engenharia_bom() -> dict[str, str]:
    return {"module": "engenharia_bom", "status": "ok"}


@router.post("/boms", response_model=BomResponse, status_code=status.HTTP_201_CREATED)
def create_bom(_: WritePermission, db: DbSession, payload: BomCreate):
    return _service(db).create_bom(payload.model_dump())


@router.get("/boms", response_model=BomListResponse)
def list_boms(
    _: ReadPermission,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    produto_final_id: int | None = Query(default=None, gt=0),
    status_filter: BomStatus | None = Query(default=None, alias="status"),
) -> dict[str, Any]:
    items, total = _service(db).list_boms(
        page=page,
        page_size=page_size,
        produto_final_id=produto_final_id,
        status_filter=status_filter.value if status_filter is not None else None,
    )
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.get("/boms/{bom_id}", response_model=BomResponse)
def get_bom(_: ReadPermission, db: DbSession, bom_id: int):
    return _service(db).get_bom_or_404(bom_id)


@router.patch("/boms/{bom_id}", response_model=BomResponse)
def update_bom(
    _: WritePermission,
    db: DbSession,
    bom_id: int,
    payload: BomUpdate,
):
    return _service(db).update_bom(bom_id=bom_id, payload=payload.model_dump(exclude_unset=True))


@router.post(
    "/boms/{bom_id}/itens",
    response_model=BomItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_bom_item(
    _: WritePermission,
    db: DbSession,
    bom_id: int,
    payload: BomItemCreate,
):
    return _service(db).create_item(bom_id=bom_id, payload=payload.model_dump())


@router.patch("/boms/{bom_id}/itens/{item_id}", response_model=BomItemResponse)
def update_bom_item(
    _: WritePermission,
    db: DbSession,
    bom_id: int,
    item_id: int,
    payload: BomItemUpdate,
):
    return _service(db).update_item(
        bom_id=bom_id,
        item_id=item_id,
        payload=payload.model_dump(exclude_unset=True),
    )


@router.delete(
    "/boms/{bom_id}/itens/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_bom_item(_: WritePermission, db: DbSession, bom_id: int, item_id: int) -> Response:
    _service(db).delete_item(bom_id=bom_id, item_id=item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/boms/{bom_id}/arvore", response_model=BomTreeResponse)
def get_bom_tree(_: ReadPermission, db: DbSession, bom_id: int):
    bom, tree = _service(db).build_tree(bom_id)
    return {"bom": bom, "tree": tree}


@router.get("/boms/{bom_id}/explosao", response_model=BomExplosionResponse)
def explode_bom(
    _: ReadPermission,
    db: DbSession,
    bom_id: int,
    quantidade_base: Decimal = Query(default=Decimal("1"), gt=0),
):
    bom, insumos, custo_total = _service(db).explode_bom(
        bom_id=bom_id,
        quantidade_base=quantidade_base,
    )
    return {
        "bom_id": bom.id,
        "produto_final_id": bom.produto_final_id,
        "quantidade_base": quantidade_base,
        "insumos": insumos,
        "custo_total_materiais": custo_total,
    }
