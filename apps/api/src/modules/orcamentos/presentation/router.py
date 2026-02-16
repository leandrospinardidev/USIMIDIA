from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import UserRole, require_roles
from modules.orcamentos.application.services import OrcamentosService
from modules.orcamentos.presentation.schemas import (
    OrcamentoAnexoListResponse,
    OrcamentoAnexoResponse,
    OrcamentoCreate,
    OrcamentoListResponse,
    OrcamentoResponse,
    OrcamentoSimulacaoResponse,
    OrcamentoStatus,
    OrcamentoStatusUpdate,
    OrcamentoVersaoCreate,
)
from shared.application.pagination import PageMeta

router = APIRouter(prefix="/orcamentos", tags=["Orcamentos"])

ReadPermission = Annotated[
    UserRole,
    Depends(require_roles(UserRole.ADMIN, UserRole.PCP, UserRole.COMPRAS)),
]
WritePermission = Annotated[
    UserRole,
    Depends(require_roles(UserRole.ADMIN, UserRole.PCP, UserRole.COMPRAS)),
]
DbSession = Annotated[Session, Depends(get_db)]


def _service(db: Session) -> OrcamentosService:
    return OrcamentosService(db)


def _paginated_response(
    items: list[Any], *, page: int, page_size: int, total: int
) -> dict[str, Any]:
    return {"items": items, "meta": PageMeta(page=page, page_size=page_size, total=total)}


@router.get("/ping")
def ping_orcamentos() -> dict[str, str]:
    return {"module": "orcamentos", "status": "ok"}


@router.post("/simulacoes", response_model=OrcamentoSimulacaoResponse)
def simular_orcamento(_: WritePermission, db: DbSession, payload: OrcamentoCreate):
    simulation_payload = payload.model_dump(
        exclude={"codigo", "referencia_projeto", "observacao", "moeda"},
        exclude_unset=True,
    )
    return _service(db).simulate(simulation_payload)


@router.post("", response_model=OrcamentoResponse, status_code=status.HTTP_201_CREATED)
def create_orcamento(_: WritePermission, db: DbSession, payload: OrcamentoCreate):
    return _service(db).create_orcamento(payload.model_dump(exclude_unset=True))


@router.post("/{orcamento_id}/versoes", response_model=OrcamentoResponse)
def create_versao_orcamento(
    _: WritePermission,
    db: DbSession,
    orcamento_id: int,
    payload: OrcamentoVersaoCreate,
):
    return _service(db).create_nova_versao(
        orcamento_id=orcamento_id,
        payload=payload.model_dump(exclude_unset=True),
    )


@router.patch("/{orcamento_id}/status", response_model=OrcamentoResponse)
def update_status_orcamento(
    _: WritePermission,
    db: DbSession,
    orcamento_id: int,
    payload: OrcamentoStatusUpdate,
):
    return _service(db).update_status(orcamento_id=orcamento_id, status_value=payload.status)


@router.get("", response_model=OrcamentoListResponse)
def list_orcamentos(
    _: ReadPermission,
    db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    search: str | None = Query(default=None, max_length=100),
    status_filter: Annotated[OrcamentoStatus | None, Query(alias="status")] = None,
) -> dict[str, Any]:
    items, total = _service(db).list_orcamentos(
        page=page,
        page_size=page_size,
        search=search,
        status_filter=status_filter.value if status_filter is not None else None,
    )
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.get("/{orcamento_id}", response_model=OrcamentoResponse)
def get_orcamento(_: ReadPermission, db: DbSession, orcamento_id: int):
    return _service(db).get_orcamento_detail(orcamento_id)


@router.post(
    "/{orcamento_id}/anexos",
    response_model=OrcamentoAnexoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_anexo_orcamento(
    _: WritePermission,
    db: DbSession,
    orcamento_id: int,
    file: UploadFile = File(...),
    observacao: str | None = Form(default=None),
):
    content = await file.read()
    return _service(db).upload_anexo(
        orcamento_id=orcamento_id,
        nome_arquivo=file.filename or "",
        content_type=file.content_type,
        observacao=observacao,
        file_bytes=content,
    )


@router.get("/{orcamento_id}/anexos", response_model=OrcamentoAnexoListResponse)
def list_anexos_orcamento(
    _: ReadPermission,
    db: DbSession,
    orcamento_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    items, total = _service(db).list_anexos(orcamento_id=orcamento_id, page=page, page_size=page_size)
    return _paginated_response(items, page=page, page_size=page_size, total=total)


@router.get("/anexos/{anexo_id}/download")
def download_anexo_orcamento(_: ReadPermission, db: DbSession, anexo_id: int):
    payload = _service(db).get_anexo_download(anexo_id=anexo_id)
    return FileResponse(
        path=payload["absolute_path"],
        media_type=payload.get("content_type") or "application/octet-stream",
        filename=payload["nome_arquivo_original"],
    )
