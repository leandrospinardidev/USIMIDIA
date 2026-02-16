from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from modules.cadastro.infrastructure.models import InsumoModel
from modules.estoque_retalhos.infrastructure.models import (
    EstoqueLoteModel,
    EstoqueMovimentacaoModel,
)

HTTP_422 = status.HTTP_422_UNPROCESSABLE_CONTENT

MOV_ENTRADA = "ENTRADA"
MOV_CONSUMO_OP = "CONSUMO_OP"
MOV_AJUSTE = "AJUSTE"
MOV_RETALHO_GERADO = "RETALHO_GERADO"
MOV_RETALHO_CONSUMIDO = "RETALHO_CONSUMIDO"

MOVIMENTOS_CONSUMO = {MOV_CONSUMO_OP, MOV_RETALHO_CONSUMIDO}


class EstoqueRetalhosService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_lote_entrada(self, payload: dict[str, Any]) -> dict[str, Any]:
        insumo_id = int(payload["insumo_id"])
        codigo_lote = str(payload["codigo_lote"]).strip()
        quantidade_inicial = self._to_decimal(payload["quantidade_inicial"], "quantidade_inicial")
        custo_total = self._to_decimal(payload.get("custo_total", Decimal("0")), "custo_total")

        if quantidade_inicial <= 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail="quantidade_inicial deve ser maior que zero.",
            )
        if custo_total < 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail="custo_total nao pode ser negativo.",
            )

        self._ensure_insumo_exists(insumo_id)
        self._ensure_codigo_lote_unique(codigo_lote)

        lote = EstoqueLoteModel(
            insumo_id=insumo_id,
            codigo_lote=codigo_lote,
            quantidade_inicial=quantidade_inicial,
            quantidade_disponivel=quantidade_inicial,
            largura_mm=self._to_optional_decimal(payload.get("largura_mm"), "largura_mm"),
            altura_mm=self._to_optional_decimal(payload.get("altura_mm"), "altura_mm"),
            espessura_mm=self._to_optional_decimal(payload.get("espessura_mm"), "espessura_mm"),
            custo_total=custo_total,
            is_retalho=bool(payload.get("is_retalho", False)),
            lote_origem_id=payload.get("lote_origem_id"),
        )
        self.db.add(lote)
        self.db.flush()

        self._create_movimentacao(
            lote_id=lote.id,
            tipo_movimento=MOV_ENTRADA,
            quantidade=quantidade_inicial,
            ordem_id=payload.get("ordem_id"),
            largura_mm=lote.largura_mm,
            altura_mm=lote.altura_mm,
            observacao=payload.get("observacao"),
        )

        self._commit_or_409("Falha ao registrar entrada de lote.")
        return self.get_lote_detail(lote.id)

    def list_lotes(
        self,
        *,
        page: int,
        page_size: int,
        insumo_id: int | None = None,
        com_saldo: bool | None = None,
        is_retalho: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(EstoqueLoteModel, InsumoModel).join(
            InsumoModel,
            InsumoModel.id == EstoqueLoteModel.insumo_id,
        )

        if insumo_id is not None:
            stmt = stmt.where(EstoqueLoteModel.insumo_id == insumo_id)
        if com_saldo is True:
            stmt = stmt.where(EstoqueLoteModel.quantidade_disponivel > 0)
        if com_saldo is False:
            stmt = stmt.where(EstoqueLoteModel.quantidade_disponivel <= 0)
        if is_retalho is not None:
            stmt = stmt.where(EstoqueLoteModel.is_retalho.is_(is_retalho))
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    EstoqueLoteModel.codigo_lote.ilike(pattern),
                    InsumoModel.codigo.ilike(pattern),
                    InsumoModel.descricao.ilike(pattern),
                )
            )

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = (
            stmt.order_by(EstoqueLoteModel.criado_em.desc(), EstoqueLoteModel.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = self.db.execute(stmt).all()
        items = [self._serialize_lote(lote, insumo) for lote, insumo in rows]
        return items, int(total)

    def get_lote_detail(self, lote_id: int) -> dict[str, Any]:
        row = self.db.execute(
            select(EstoqueLoteModel, InsumoModel)
            .join(InsumoModel, InsumoModel.id == EstoqueLoteModel.insumo_id)
            .where(EstoqueLoteModel.id == lote_id)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lote nao encontrado.",
            )
        lote, insumo = row
        return self._serialize_lote(lote, insumo)

    def consumir_lote(self, *, lote_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        lote = self._get_lote_or_404(lote_id)
        quantidade = self._to_decimal(payload["quantidade"], "quantidade")
        if quantidade <= 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail="quantidade deve ser maior que zero.",
            )
        if Decimal(lote.quantidade_disponivel) < quantidade:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Saldo insuficiente no lote.",
            )

        tipo_movimento = self._resolve_tipo_consumo(
            tipo_movimento=payload.get("tipo_movimento"),
            is_retalho=bool(lote.is_retalho),
        )
        lote.quantidade_disponivel = Decimal(lote.quantidade_disponivel) - quantidade

        self._create_movimentacao(
            lote_id=lote.id,
            tipo_movimento=tipo_movimento,
            quantidade=quantidade,
            ordem_id=payload.get("ordem_id"),
            largura_mm=self._to_optional_decimal(payload.get("largura_mm"), "largura_mm"),
            altura_mm=self._to_optional_decimal(payload.get("altura_mm"), "altura_mm"),
            observacao=payload.get("observacao"),
        )
        self._commit_or_409("Falha ao registrar consumo do lote.")
        return self.get_lote_detail(lote.id)

    def gerar_retalho(self, *, lote_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        lote_origem = self._get_lote_or_404(lote_id)
        quantidade = self._to_decimal(payload["quantidade"], "quantidade")
        if quantidade <= 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail="quantidade deve ser maior que zero.",
            )
        if Decimal(lote_origem.quantidade_disponivel) < quantidade:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Saldo insuficiente para gerar retalho.",
            )

        codigo_lote_retalho = str(payload["codigo_lote_retalho"]).strip()
        self._ensure_codigo_lote_unique(codigo_lote_retalho)

        custo_total_retalho = self._rateio_custo(
            custo_total_lote=Decimal(lote_origem.custo_total),
            quantidade_inicial=Decimal(lote_origem.quantidade_inicial),
            quantidade_retalho=quantidade,
        )
        largura_mm = self._to_optional_decimal(payload.get("largura_mm"), "largura_mm")
        altura_mm = self._to_optional_decimal(payload.get("altura_mm"), "altura_mm")

        lote_origem.quantidade_disponivel = Decimal(lote_origem.quantidade_disponivel) - quantidade

        retalho = EstoqueLoteModel(
            insumo_id=lote_origem.insumo_id,
            codigo_lote=codigo_lote_retalho,
            quantidade_inicial=quantidade,
            quantidade_disponivel=quantidade,
            largura_mm=largura_mm if largura_mm is not None else lote_origem.largura_mm,
            altura_mm=altura_mm if altura_mm is not None else lote_origem.altura_mm,
            espessura_mm=lote_origem.espessura_mm,
            custo_total=custo_total_retalho,
            is_retalho=True,
            lote_origem_id=lote_origem.id,
        )
        self.db.add(retalho)
        self.db.flush()

        self._create_movimentacao(
            lote_id=lote_origem.id,
            tipo_movimento=MOV_RETALHO_GERADO,
            quantidade=quantidade,
            ordem_id=payload.get("ordem_id"),
            largura_mm=retalho.largura_mm,
            altura_mm=retalho.altura_mm,
            observacao=payload.get("observacao"),
        )
        self._create_movimentacao(
            lote_id=retalho.id,
            tipo_movimento=MOV_ENTRADA,
            quantidade=quantidade,
            ordem_id=payload.get("ordem_id"),
            largura_mm=retalho.largura_mm,
            altura_mm=retalho.altura_mm,
            observacao=f"Retalho gerado do lote {lote_origem.codigo_lote}",
        )

        self._commit_or_409("Falha ao gerar retalho.")
        return {
            "lote_origem": self.get_lote_detail(lote_origem.id),
            "lote_retalho": self.get_lote_detail(retalho.id),
        }

    def ajustar_lote(self, *, lote_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        lote = self._get_lote_or_404(lote_id)
        delta = self._to_decimal(payload["delta_quantidade"], "delta_quantidade")
        if delta == 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail="delta_quantidade nao pode ser zero.",
            )

        saldo_novo = Decimal(lote.quantidade_disponivel) + delta
        if saldo_novo < 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ajuste deixaria o lote com saldo negativo.",
            )

        lote.quantidade_disponivel = saldo_novo
        sinal = "+" if delta > 0 else "-"
        observacao = payload.get("observacao")
        observacao_ajuste = f"AJUSTE({sinal})"
        if observacao:
            observacao_ajuste = f"{observacao_ajuste}: {observacao}"

        self._create_movimentacao(
            lote_id=lote.id,
            tipo_movimento=MOV_AJUSTE,
            quantidade=abs(delta),
            ordem_id=payload.get("ordem_id"),
            largura_mm=self._to_optional_decimal(payload.get("largura_mm"), "largura_mm"),
            altura_mm=self._to_optional_decimal(payload.get("altura_mm"), "altura_mm"),
            observacao=observacao_ajuste,
        )
        self._commit_or_409("Falha ao ajustar lote.")
        return self.get_lote_detail(lote.id)

    def list_movimentacoes(
        self,
        *,
        lote_id: int,
        page: int,
        page_size: int,
        tipo_movimento: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        self._get_lote_or_404(lote_id)
        stmt = select(EstoqueMovimentacaoModel).where(EstoqueMovimentacaoModel.lote_id == lote_id)

        if tipo_movimento:
            stmt = stmt.where(EstoqueMovimentacaoModel.tipo_movimento == tipo_movimento)

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = (
            stmt.order_by(
                EstoqueMovimentacaoModel.data_hora.desc(),
                EstoqueMovimentacaoModel.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._serialize_movimentacao(mov) for mov in self.db.scalars(stmt).all()]
        return items, int(total)

    def saldos_por_insumo(self, *, only_positive: bool = False) -> list[dict[str, Any]]:
        saldo_expr = func.coalesce(func.sum(EstoqueLoteModel.quantidade_disponivel), Decimal("0"))
        lotes_com_saldo_expr = func.coalesce(
            func.sum(case((EstoqueLoteModel.quantidade_disponivel > 0, 1), else_=0)),
            0,
        )

        stmt = (
            select(
                InsumoModel.id,
                InsumoModel.codigo,
                InsumoModel.descricao,
                InsumoModel.unidade_medida,
                saldo_expr.label("saldo_disponivel"),
                lotes_com_saldo_expr.label("lotes_com_saldo"),
            )
            .join(EstoqueLoteModel, EstoqueLoteModel.insumo_id == InsumoModel.id, isouter=True)
            .group_by(
                InsumoModel.id,
                InsumoModel.codigo,
                InsumoModel.descricao,
                InsumoModel.unidade_medida,
            )
            .order_by(InsumoModel.codigo)
        )
        if only_positive:
            stmt = stmt.having(saldo_expr > 0)

        rows = self.db.execute(stmt).all()
        return [
            {
                "insumo_id": row.id,
                "codigo": row.codigo,
                "descricao": row.descricao,
                "unidade_medida": row.unidade_medida,
                "saldo_disponivel": row.saldo_disponivel,
                "lotes_com_saldo": int(row.lotes_com_saldo or 0),
            }
            for row in rows
        ]

    def _get_lote_or_404(self, lote_id: int) -> EstoqueLoteModel:
        lote = self.db.get(EstoqueLoteModel, lote_id)
        if lote is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lote nao encontrado.",
            )
        return lote

    def _ensure_insumo_exists(self, insumo_id: int) -> InsumoModel:
        insumo = self.db.get(InsumoModel, insumo_id)
        if insumo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Insumo nao encontrado.",
            )
        return insumo

    def _ensure_codigo_lote_unique(self, codigo_lote: str) -> None:
        existing_id = self.db.scalar(
            select(EstoqueLoteModel.id).where(EstoqueLoteModel.codigo_lote == codigo_lote)
        )
        if existing_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="codigo_lote ja cadastrado.",
            )

    def _resolve_tipo_consumo(self, *, tipo_movimento: Any, is_retalho: bool) -> str:
        if tipo_movimento is None:
            return MOV_RETALHO_CONSUMIDO if is_retalho else MOV_CONSUMO_OP

        tipo = self._enum_to_str(tipo_movimento)
        if tipo not in MOVIMENTOS_CONSUMO:
            raise HTTPException(
                status_code=HTTP_422,
                detail="tipo_movimento invalido para consumo.",
            )
        return tipo

    def _create_movimentacao(
        self,
        *,
        lote_id: int,
        tipo_movimento: str,
        quantidade: Decimal,
        ordem_id: int | None = None,
        largura_mm: Decimal | None = None,
        altura_mm: Decimal | None = None,
        observacao: str | None = None,
    ) -> EstoqueMovimentacaoModel:
        movimentacao = EstoqueMovimentacaoModel(
            lote_id=lote_id,
            ordem_id=ordem_id,
            tipo_movimento=tipo_movimento,
            quantidade=quantidade,
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            observacao=observacao,
        )
        self.db.add(movimentacao)
        return movimentacao

    def _serialize_lote(self, lote: EstoqueLoteModel, insumo: InsumoModel) -> dict[str, Any]:
        return {
            "id": lote.id,
            "insumo_id": lote.insumo_id,
            "insumo_codigo": insumo.codigo,
            "insumo_descricao": insumo.descricao,
            "unidade_medida": insumo.unidade_medida,
            "codigo_lote": lote.codigo_lote,
            "quantidade_inicial": lote.quantidade_inicial,
            "quantidade_disponivel": lote.quantidade_disponivel,
            "largura_mm": lote.largura_mm,
            "altura_mm": lote.altura_mm,
            "espessura_mm": lote.espessura_mm,
            "custo_total": lote.custo_total,
            "is_retalho": lote.is_retalho,
            "lote_origem_id": lote.lote_origem_id,
            "criado_em": lote.criado_em,
        }

    def _serialize_movimentacao(self, mov: EstoqueMovimentacaoModel) -> dict[str, Any]:
        return {
            "id": mov.id,
            "lote_id": mov.lote_id,
            "ordem_id": mov.ordem_id,
            "tipo_movimento": mov.tipo_movimento,
            "quantidade": mov.quantidade,
            "largura_mm": mov.largura_mm,
            "altura_mm": mov.altura_mm,
            "data_hora": mov.data_hora,
            "observacao": mov.observacao,
        }

    def _to_decimal(self, value: Any, field_name: str) -> Decimal:
        try:
            return Decimal(str(value))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=HTTP_422,
                detail=f"Valor invalido para {field_name}.",
            ) from exc

    def _to_optional_decimal(self, value: Any, field_name: str) -> Decimal | None:
        if value is None:
            return None
        parsed = self._to_decimal(value, field_name)
        if parsed < 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail=f"{field_name} nao pode ser negativo.",
            )
        return parsed

    def _rateio_custo(
        self,
        *,
        custo_total_lote: Decimal,
        quantidade_inicial: Decimal,
        quantidade_retalho: Decimal,
    ) -> Decimal:
        if quantidade_inicial <= 0:
            return Decimal("0")
        custo_unitario = custo_total_lote / quantidade_inicial
        return custo_unitario * quantidade_retalho

    def _enum_to_str(self, value: Any) -> str:
        if isinstance(value, Enum):
            return str(value.value)
        return str(value)

    def _commit_or_409(self, message: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            detail = message
            if "codigo_lote" in str(exc.orig):
                detail = "codigo_lote ja cadastrado."
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
