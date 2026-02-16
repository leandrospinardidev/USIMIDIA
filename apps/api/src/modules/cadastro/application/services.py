from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class CrudService(Generic[ModelT]):
    def __init__(
        self,
        db: Session,
        model: type[ModelT],
        resource_name: str,
        search_fields: list[Any],
    ) -> None:
        self.db = db
        self.model = model
        self.resource_name = resource_name
        self.search_fields = search_fields

    def list(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        ativo: bool | None = None,
    ) -> tuple[list[ModelT], int]:
        stmt = select(self.model)

        if search:
            pattern = f"%{search}%"
            filters = [field.ilike(pattern) for field in self.search_fields]
            stmt = stmt.where(or_(*filters))

        if ativo is not None and hasattr(self.model, "ativo"):
            stmt = stmt.where(self.model.ativo.is_(ativo))

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = (
            stmt.order_by(self.model.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self.db.scalars(stmt).all())
        return items, total

    def get_or_404(self, resource_id: int) -> ModelT:
        entity = self.db.get(self.model, resource_id)
        if entity is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.resource_name.capitalize()} nao encontrado.",
            )
        return entity

    def create(self, payload: dict[str, Any]) -> ModelT:
        codigo = payload.get("codigo")
        if codigo:
            self._ensure_codigo_unique(codigo=codigo)

        entity = self.model(**payload)
        self.db.add(entity)
        self._commit_or_409()
        self.db.refresh(entity)
        return entity

    def update(self, resource_id: int, payload: dict[str, Any]) -> ModelT:
        entity = self.get_or_404(resource_id)
        codigo = payload.get("codigo")

        if codigo and codigo != entity.codigo:
            self._ensure_codigo_unique(codigo=codigo, exclude_id=resource_id)

        for field, value in payload.items():
            setattr(entity, field, value)

        if hasattr(entity, "updated_at"):
            entity.updated_at = datetime.now(UTC)

        self._commit_or_409()
        self.db.refresh(entity)
        return entity

    def soft_delete(self, resource_id: int) -> None:
        entity = self.get_or_404(resource_id)

        if hasattr(entity, "ativo"):
            entity.ativo = False

        if hasattr(entity, "updated_at"):
            entity.updated_at = datetime.now(UTC)

        self._commit_or_409()

    def _ensure_codigo_unique(self, *, codigo: str, exclude_id: int | None = None) -> None:
        stmt = select(self.model.id).where(self.model.codigo == codigo)
        if exclude_id is not None:
            stmt = stmt.where(self.model.id != exclude_id)

        already_exists = self.db.scalar(stmt)
        if already_exists is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Codigo ja cadastrado para {self.resource_name}.",
            )

    def _commit_or_409(self) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Violacao de integridade no cadastro de {self.resource_name}.",
            ) from exc
