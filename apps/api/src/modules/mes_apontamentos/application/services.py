from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from modules.mes_apontamentos.infrastructure.models import (
    ApontamentoProducaoModel,
    RefugoProducaoModel,
)
from modules.ordens_producao.infrastructure.models import OrdemOperacaoModel, OrdemProducaoModel

HTTP_422 = status.HTTP_422_UNPROCESSABLE_CONTENT

STATUS_OPERACAO_EVENTOS = {
    "PENDENTE": {"START"},
    "EM_EXECUCAO": {"PAUSA", "STOP"},
    "PAUSADA": {"RETOMADA", "STOP"},
    "CONCLUIDA": set(),
}


class MesApontamentosService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar_evento(self, *, ordem_operacao_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        operacao = self._get_operacao_or_404(ordem_operacao_id)
        ordem = self._get_ordem_or_404(operacao.ordem_id)

        evento = self._enum_to_str(payload["evento"])
        if evento not in {"START", "STOP", "PAUSA", "RETOMADA"}:
            raise HTTPException(
                status_code=HTTP_422,
                detail="evento invalido para apontamento MES.",
            )

        allowed_events = STATUS_OPERACAO_EVENTOS.get(operacao.status, set())
        if evento not in allowed_events:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Evento {evento} invalido para operacao em status {operacao.status}.",
            )

        data_hora_evento = self._normalize_datetime(payload.get("data_hora_evento") or datetime.now(UTC))
        last_event = self._last_event(ordem_operacao_id)
        if last_event is not None and data_hora_evento < last_event.data_hora_evento:
            raise HTTPException(
                status_code=HTTP_422,
                detail="data_hora_evento nao pode ser menor que o ultimo evento.",
            )

        quantidade_produzida = self._to_decimal(payload.get("quantidade_produzida", Decimal("0")))
        if quantidade_produzida < 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail="quantidade_produzida nao pode ser negativa.",
            )

        apontamento = ApontamentoProducaoModel(
            ordem_operacao_id=operacao.id,
            evento=evento,
            data_hora_evento=data_hora_evento,
            motivo=payload.get("motivo"),
            quantidade_produzida=quantidade_produzida,
        )
        self.db.add(apontamento)

        self._apply_operacao_status_from_event(operacao=operacao, evento=evento)
        if quantidade_produzida > 0:
            ordem.quantidade_produzida = Decimal(ordem.quantidade_produzida) + quantidade_produzida

        self._recalculate_status_ordem(ordem)
        ordem.updated_at = datetime.now(UTC)

        self._commit_or_409("Falha ao registrar apontamento MES.")
        self.db.refresh(apontamento)
        return self._serialize_apontamento(apontamento, operacao=operacao, ordem=ordem)

    def list_eventos(
        self,
        *,
        ordem_operacao_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        operacao = self._get_operacao_or_404(ordem_operacao_id)
        ordem = self._get_ordem_or_404(operacao.ordem_id)

        stmt = select(ApontamentoProducaoModel).where(
            ApontamentoProducaoModel.ordem_operacao_id == ordem_operacao_id
        )
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = (
            stmt.order_by(ApontamentoProducaoModel.data_hora_evento.desc(), ApontamentoProducaoModel.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [
            self._serialize_apontamento(item, operacao=operacao, ordem=ordem)
            for item in self.db.scalars(stmt).all()
        ]
        return items, int(total)

    def registrar_refugo(self, *, ordem_operacao_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        operacao = self._get_operacao_or_404(ordem_operacao_id)
        ordem = self._get_ordem_or_404(operacao.ordem_id)

        quantidade = self._to_decimal(payload["quantidade"])
        if quantidade <= 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail="quantidade de refugo deve ser maior que zero.",
            )

        data_hora = self._normalize_datetime(payload.get("data_hora") or datetime.now(UTC))
        refugo = RefugoProducaoModel(
            ordem_operacao_id=operacao.id,
            quantidade=quantidade,
            motivo=str(payload["motivo"]).strip(),
            data_hora=data_hora,
        )
        self.db.add(refugo)

        ordem.quantidade_refugada = Decimal(ordem.quantidade_refugada) + quantidade
        ordem.updated_at = datetime.now(UTC)

        self._commit_or_409("Falha ao registrar refugo.")
        self.db.refresh(refugo)
        return self._serialize_refugo(refugo=refugo, ordem=ordem)

    def list_refugos(
        self,
        *,
        ordem_operacao_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        operacao = self._get_operacao_or_404(ordem_operacao_id)
        ordem = self._get_ordem_or_404(operacao.ordem_id)

        stmt = select(RefugoProducaoModel).where(RefugoProducaoModel.ordem_operacao_id == ordem_operacao_id)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = (
            stmt.order_by(RefugoProducaoModel.data_hora.desc(), RefugoProducaoModel.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._serialize_refugo(refugo=item, ordem=ordem) for item in self.db.scalars(stmt).all()]
        return items, int(total)

    def resumo_tempo_operacao(self, *, ordem_operacao_id: int) -> dict[str, Any]:
        operacao = self._get_operacao_or_404(ordem_operacao_id)
        ordem = self._get_ordem_or_404(operacao.ordem_id)

        eventos = list(
            self.db.scalars(
                select(ApontamentoProducaoModel)
                .where(ApontamentoProducaoModel.ordem_operacao_id == ordem_operacao_id)
                .order_by(ApontamentoProducaoModel.data_hora_evento.asc(), ApontamentoProducaoModel.id.asc())
            ).all()
        )
        refugos_total = self.db.scalar(
            select(func.coalesce(func.sum(RefugoProducaoModel.quantidade), Decimal("0"))).where(
                RefugoProducaoModel.ordem_operacao_id == ordem_operacao_id
            )
        ) or Decimal("0")

        total_seconds = Decimal("0")
        active_since: datetime | None = None
        for evento in eventos:
            if evento.evento in {"START", "RETOMADA"}:
                active_since = evento.data_hora_evento
            elif evento.evento in {"PAUSA", "STOP"} and active_since is not None:
                delta = Decimal((evento.data_hora_evento - active_since).total_seconds())
                if delta > 0:
                    total_seconds += delta
                active_since = None

        if active_since is not None:
            delta = Decimal((datetime.now(UTC) - active_since).total_seconds())
            if delta > 0:
                total_seconds += delta

        quantidade_produzida_total = sum(
            (Decimal(evento.quantidade_produzida) for evento in eventos),
            start=Decimal("0"),
        )
        ultimo_evento = eventos[-1] if eventos else None

        return {
            "ordem_operacao_id": operacao.id,
            "ordem_id": ordem.id,
            "status_operacao": operacao.status,
            "status_ordem": ordem.status,
            "quantidade_eventos": len(eventos),
            "ultimo_evento": ultimo_evento.evento if ultimo_evento else None,
            "ultima_data_hora": ultimo_evento.data_hora_evento if ultimo_evento else None,
            "total_segundos": total_seconds,
            "total_horas": total_seconds / Decimal("3600"),
            "quantidade_produzida_total": quantidade_produzida_total,
            "quantidade_refugada_total": Decimal(refugos_total),
        }

    def _apply_operacao_status_from_event(self, *, operacao: OrdemOperacaoModel, evento: str) -> None:
        if evento in {"START", "RETOMADA"}:
            operacao.status = "EM_EXECUCAO"
        elif evento == "PAUSA":
            operacao.status = "PAUSADA"
        elif evento == "STOP":
            operacao.status = "CONCLUIDA"
        operacao.updated_at = datetime.now(UTC)

    def _recalculate_status_ordem(self, ordem: OrdemProducaoModel) -> None:
        status_operacoes = list(
            self.db.scalars(
                select(OrdemOperacaoModel.status).where(OrdemOperacaoModel.ordem_id == ordem.id)
            ).all()
        )
        if not status_operacoes:
            return

        new_status = ordem.status
        if any(status_op == "EM_EXECUCAO" for status_op in status_operacoes):
            new_status = "EM_PRODUCAO"
            if ordem.inicio_real is None:
                ordem.inicio_real = datetime.now(UTC)
        elif any(status_op == "PAUSADA" for status_op in status_operacoes):
            new_status = "PAUSADA"
        elif all(status_op == "CONCLUIDA" for status_op in status_operacoes):
            new_status = "FINALIZADA"
            if ordem.fim_real is None:
                ordem.fim_real = datetime.now(UTC)
        elif any(status_op == "PENDENTE" for status_op in status_operacoes):
            new_status = "PLANEJADA"

        ordem.status = new_status

    def _last_event(self, ordem_operacao_id: int) -> ApontamentoProducaoModel | None:
        return self.db.scalar(
            select(ApontamentoProducaoModel)
            .where(ApontamentoProducaoModel.ordem_operacao_id == ordem_operacao_id)
            .order_by(ApontamentoProducaoModel.data_hora_evento.desc(), ApontamentoProducaoModel.id.desc())
            .limit(1)
        )

    def _serialize_apontamento(
        self,
        apontamento: ApontamentoProducaoModel,
        *,
        operacao: OrdemOperacaoModel,
        ordem: OrdemProducaoModel,
    ) -> dict[str, Any]:
        return {
            "id": apontamento.id,
            "ordem_operacao_id": apontamento.ordem_operacao_id,
            "ordem_id": ordem.id,
            "evento": apontamento.evento,
            "data_hora_evento": apontamento.data_hora_evento,
            "motivo": apontamento.motivo,
            "quantidade_produzida": apontamento.quantidade_produzida,
            "status_operacao": operacao.status,
            "status_ordem": ordem.status,
            "created_at": apontamento.created_at,
        }

    def _serialize_refugo(
        self,
        *,
        refugo: RefugoProducaoModel,
        ordem: OrdemProducaoModel,
    ) -> dict[str, Any]:
        return {
            "id": refugo.id,
            "ordem_operacao_id": refugo.ordem_operacao_id,
            "ordem_id": ordem.id,
            "quantidade": refugo.quantidade,
            "motivo": refugo.motivo,
            "data_hora": refugo.data_hora,
            "quantidade_refugada_total_ordem": ordem.quantidade_refugada,
        }

    def _get_operacao_or_404(self, ordem_operacao_id: int) -> OrdemOperacaoModel:
        operacao = self.db.get(OrdemOperacaoModel, ordem_operacao_id)
        if operacao is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Operacao de ordem nao encontrada.",
            )
        return operacao

    def _get_ordem_or_404(self, ordem_id: int) -> OrdemProducaoModel:
        ordem = self.db.get(OrdemProducaoModel, ordem_id)
        if ordem is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ordem de producao nao encontrada.",
            )
        return ordem

    def _to_decimal(self, value: Any) -> Decimal:
        try:
            return Decimal(str(value))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=HTTP_422,
                detail="Valor decimal invalido.",
            ) from exc

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _enum_to_str(self, value: Any) -> str:
        if isinstance(value, Enum):
            return str(value.value)
        return str(value)

    def _commit_or_409(self, message: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=message,
            ) from exc
