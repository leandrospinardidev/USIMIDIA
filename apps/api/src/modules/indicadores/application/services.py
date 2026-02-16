from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from modules.cadastro.infrastructure.models import (
    CentroTrabalhoModel,
    ClienteModel,
    InsumoModel,
    ProdutoFinalModel,
)
from modules.estoque_retalhos.infrastructure.models import (
    EstoqueLoteModel,
    EstoqueMovimentacaoModel,
)
from modules.mes_apontamentos.infrastructure.models import (
    ApontamentoProducaoModel,
    RefugoProducaoModel,
)
from modules.orcamentos.infrastructure.models import OrcamentoModel, OrcamentoVersaoModel
from modules.ordens_producao.infrastructure.models import OrdemOperacaoModel, OrdemProducaoModel

MOVIMENTOS_CONSUMO = {"CONSUMO_OP", "RETALHO_CONSUMIDO"}


class IndicadoresService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def kpis_gerais(
        self,
        *,
        periodo_inicio: date | None,
        periodo_fim: date | None,
        centro_trabalho_id: int | None,
        ordem_id: int | None,
        status_filter: str | None,
    ) -> dict[str, Any]:
        ordens = self._load_ordens_filtradas(
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            centro_trabalho_id=centro_trabalho_id,
            ordem_id=ordem_id,
            status_filter=status_filter,
        )
        metricas = [self._metricas_ordem(ordem) for ordem in ordens]

        quantidade_planejada_total = sum(
            (Decimal(ordem.quantidade_planejada) for ordem in ordens),
            start=Decimal("0"),
        )
        quantidade_produzida_total = sum(
            (Decimal(ordem.quantidade_produzida) for ordem in ordens),
            start=Decimal("0"),
        )
        quantidade_refugada_total = sum(
            (Decimal(ordem.quantidade_refugada) for ordem in ordens),
            start=Decimal("0"),
        )

        tempo_planejado_horas = sum(
            (item["tempo_planejado_horas"] for item in metricas),
            start=Decimal("0"),
        )
        tempo_real_horas = sum(
            (item["tempo_real_horas"] for item in metricas),
            start=Decimal("0"),
        )
        custo_material_planejado = sum(
            (item["custo_material_planejado"] for item in metricas),
            start=Decimal("0"),
        )
        custo_material_real = sum(
            (item["custo_material_real"] for item in metricas),
            start=Decimal("0"),
        )
        custo_maquina_planejado = sum(
            (item["custo_maquina_planejado"] for item in metricas),
            start=Decimal("0"),
        )
        custo_maquina_real = sum(
            (item["custo_maquina_real"] for item in metricas),
            start=Decimal("0"),
        )
        custo_total_planejado = custo_material_planejado + custo_maquina_planejado
        custo_total_real = custo_material_real + custo_maquina_real

        base_refugo = quantidade_produzida_total + quantidade_refugada_total
        refugo_pct = (
            (quantidade_refugada_total / base_refugo) * Decimal("100")
            if base_refugo > 0
            else Decimal("0")
        )
        eficiencia_pct = (
            (tempo_planejado_horas / tempo_real_horas) * Decimal("100")
            if tempo_real_horas > 0
            else Decimal("0")
        )

        custos_orcados = [item["custo_total_orcado"] for item in metricas if item["custo_total_orcado"] is not None]
        if custos_orcados:
            custo_total_orcado = sum(custos_orcados, start=Decimal("0"))
            desvio = custo_total_real - custo_total_orcado
        else:
            custo_total_orcado = None
            desvio = None

        return {
            "periodo_inicio": periodo_inicio,
            "periodo_fim": periodo_fim,
            "total_ordens": len(ordens),
            "quantidade_planejada_total": quantidade_planejada_total,
            "quantidade_produzida_total": quantidade_produzida_total,
            "quantidade_refugada_total": quantidade_refugada_total,
            "refugo_pct": refugo_pct,
            "tempo_planejado_horas": tempo_planejado_horas,
            "tempo_real_horas": tempo_real_horas,
            "eficiencia_pct": eficiencia_pct,
            "custo_material_planejado": custo_material_planejado,
            "custo_material_real": custo_material_real,
            "custo_maquina_planejado": custo_maquina_planejado,
            "custo_maquina_real": custo_maquina_real,
            "custo_total_planejado": custo_total_planejado,
            "custo_total_real": custo_total_real,
            "custo_total_orcado": custo_total_orcado,
            "desvio_custo_real_vs_orcado": desvio,
        }

    def indicadores_por_ordem(
        self,
        *,
        page: int,
        page_size: int,
        periodo_inicio: date | None,
        periodo_fim: date | None,
        centro_trabalho_id: int | None,
        status_filter: str | None,
        search: str | None,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = (
            select(OrdemProducaoModel, ProdutoFinalModel, ClienteModel)
            .join(
                ProdutoFinalModel,
                ProdutoFinalModel.id == OrdemProducaoModel.produto_final_id,
            )
            .join(
                ClienteModel,
                ClienteModel.id == OrdemProducaoModel.cliente_id,
                isouter=True,
            )
        )
        stmt = self._apply_order_filters(
            stmt=stmt,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            centro_trabalho_id=centro_trabalho_id,
            status_filter=status_filter,
            search=search,
        )

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = (
            stmt.order_by(OrdemProducaoModel.data_emissao.desc(), OrdemProducaoModel.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = self.db.execute(stmt).all()

        items: list[dict[str, Any]] = []
        for ordem, produto, cliente in rows:
            metrica = self._metricas_ordem(ordem)
            items.append(
                {
                    "ordem_id": ordem.id,
                    "numero_op": ordem.numero_op,
                    "status": ordem.status,
                    "data_emissao": ordem.data_emissao,
                    "produto_codigo": produto.codigo,
                    "produto_descricao": produto.descricao,
                    "cliente_nome": cliente.razao_social if cliente else None,
                    "quantidade_planejada": ordem.quantidade_planejada,
                    "quantidade_produzida": ordem.quantidade_produzida,
                    "quantidade_refugada": ordem.quantidade_refugada,
                    **metrica,
                }
            )
        return items, int(total)

    def rastreabilidade_ordem(self, ordem_id: int) -> dict[str, Any]:
        row = self.db.execute(
            select(OrdemProducaoModel, ProdutoFinalModel, ClienteModel)
            .join(
                ProdutoFinalModel,
                ProdutoFinalModel.id == OrdemProducaoModel.produto_final_id,
            )
            .join(
                ClienteModel,
                ClienteModel.id == OrdemProducaoModel.cliente_id,
                isouter=True,
            )
            .where(OrdemProducaoModel.id == ordem_id)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ordem de producao nao encontrada para rastreabilidade.",
            )
        ordem, produto, cliente = row

        operacoes = self._resumo_operacoes_ordem(ordem.id)
        movimentacoes = self._movimentacoes_ordem(ordem.id)
        lotes_relacionados, fluxo_retalhos = self._rastrear_lotes(movimentacoes)

        return {
            "ordem_id": ordem.id,
            "numero_op": ordem.numero_op,
            "status": ordem.status,
            "data_emissao": ordem.data_emissao,
            "produto_codigo": produto.codigo,
            "produto_descricao": produto.descricao,
            "cliente_nome": cliente.razao_social if cliente else None,
            "quantidade_planejada": ordem.quantidade_planejada,
            "quantidade_produzida": ordem.quantidade_produzida,
            "quantidade_refugada": ordem.quantidade_refugada,
            "bom_snapshot_json": ordem.bom_snapshot_json or {},
            "operacoes": operacoes,
            "movimentacoes": movimentacoes,
            "lotes_relacionados": lotes_relacionados,
            "fluxo_retalhos": fluxo_retalhos,
        }

    def _load_ordens_filtradas(
        self,
        *,
        periodo_inicio: date | None,
        periodo_fim: date | None,
        centro_trabalho_id: int | None,
        ordem_id: int | None,
        status_filter: str | None,
    ) -> list[OrdemProducaoModel]:
        stmt = select(OrdemProducaoModel)
        if ordem_id is not None:
            stmt = stmt.where(OrdemProducaoModel.id == ordem_id)
        if periodo_inicio is not None:
            stmt = stmt.where(OrdemProducaoModel.data_emissao >= periodo_inicio)
        if periodo_fim is not None:
            stmt = stmt.where(OrdemProducaoModel.data_emissao <= periodo_fim)
        if status_filter is not None:
            stmt = stmt.where(OrdemProducaoModel.status == status_filter)
        if centro_trabalho_id is not None:
            subquery = (
                select(OrdemOperacaoModel.ordem_id)
                .where(OrdemOperacaoModel.centro_trabalho_id == centro_trabalho_id)
                .distinct()
            )
            stmt = stmt.where(OrdemProducaoModel.id.in_(subquery))
        stmt = stmt.order_by(OrdemProducaoModel.id)
        return list(self.db.scalars(stmt).all())

    def _apply_order_filters(
        self,
        *,
        stmt,
        periodo_inicio: date | None,
        periodo_fim: date | None,
        centro_trabalho_id: int | None,
        status_filter: str | None,
        search: str | None,
    ):
        if periodo_inicio is not None:
            stmt = stmt.where(OrdemProducaoModel.data_emissao >= periodo_inicio)
        if periodo_fim is not None:
            stmt = stmt.where(OrdemProducaoModel.data_emissao <= periodo_fim)
        if status_filter is not None:
            stmt = stmt.where(OrdemProducaoModel.status == status_filter)
        if centro_trabalho_id is not None:
            subquery = (
                select(OrdemOperacaoModel.ordem_id)
                .where(OrdemOperacaoModel.centro_trabalho_id == centro_trabalho_id)
                .distinct()
            )
            stmt = stmt.where(OrdemProducaoModel.id.in_(subquery))
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    OrdemProducaoModel.numero_op.ilike(pattern),
                    ProdutoFinalModel.codigo.ilike(pattern),
                    ProdutoFinalModel.descricao.ilike(pattern),
                    ClienteModel.razao_social.ilike(pattern),
                )
            )
        return stmt

    def _metricas_ordem(self, ordem: OrdemProducaoModel) -> dict[str, Decimal | None]:
        op_rows = self.db.execute(
            select(OrdemOperacaoModel, CentroTrabalhoModel)
            .join(
                CentroTrabalhoModel,
                CentroTrabalhoModel.id == OrdemOperacaoModel.centro_trabalho_id,
            )
            .where(OrdemOperacaoModel.ordem_id == ordem.id)
            .order_by(OrdemOperacaoModel.sequencia)
        ).all()

        qtd_planejada = Decimal(ordem.quantidade_planejada)
        tempo_planejado_horas = Decimal("0")
        tempo_real_horas = Decimal("0")
        custo_maquina_planejado = Decimal("0")
        custo_maquina_real = Decimal("0")

        for operacao, centro in op_rows:
            taxa_horaria = Decimal(centro.taxa_horaria)
            tempo_planejado_min = Decimal(operacao.setup_planejado_min) + (
                Decimal(operacao.ciclo_planejado_min) * qtd_planejada
            )
            tempo_planejado_op_horas = tempo_planejado_min / Decimal("60")
            tempo_planejado_horas += tempo_planejado_op_horas
            custo_maquina_planejado += tempo_planejado_op_horas * taxa_horaria

            tempo_real_seg = self._tempo_real_segundos_operacao(operacao.id)
            tempo_real_op_horas = tempo_real_seg / Decimal("3600")
            tempo_real_horas += tempo_real_op_horas
            custo_maquina_real += tempo_real_op_horas * taxa_horaria

        custo_material_planejado = self._snapshot_material_cost(ordem.bom_snapshot_json or {})
        custo_material_real = self._custo_material_real_ordem(ordem.id)
        custo_total_planejado = custo_material_planejado + custo_maquina_planejado
        custo_total_real = custo_material_real + custo_maquina_real

        qtd_produzida = Decimal(ordem.quantidade_produzida)
        qtd_refugada = Decimal(ordem.quantidade_refugada)
        base_refugo = qtd_produzida + qtd_refugada
        refugo_pct = (
            (qtd_refugada / base_refugo) * Decimal("100")
            if base_refugo > 0
            else Decimal("0")
        )
        eficiencia_pct = (
            (tempo_planejado_horas / tempo_real_horas) * Decimal("100")
            if tempo_real_horas > 0
            else Decimal("0")
        )

        custo_total_orcado = self._custo_orcado_total_produto(ordem.produto_final_id)
        if custo_total_orcado is not None:
            desvio = custo_total_real - custo_total_orcado
        else:
            desvio = None

        return {
            "refugo_pct": refugo_pct,
            "tempo_planejado_horas": tempo_planejado_horas,
            "tempo_real_horas": tempo_real_horas,
            "eficiencia_pct": eficiencia_pct,
            "custo_material_planejado": custo_material_planejado,
            "custo_material_real": custo_material_real,
            "custo_maquina_planejado": custo_maquina_planejado,
            "custo_maquina_real": custo_maquina_real,
            "custo_total_planejado": custo_total_planejado,
            "custo_total_real": custo_total_real,
            "custo_total_orcado": custo_total_orcado,
            "desvio_custo_real_vs_orcado": desvio,
        }

    def _tempo_real_segundos_operacao(self, ordem_operacao_id: int) -> Decimal:
        eventos = list(
            self.db.scalars(
                select(ApontamentoProducaoModel)
                .where(ApontamentoProducaoModel.ordem_operacao_id == ordem_operacao_id)
                .order_by(
                    ApontamentoProducaoModel.data_hora_evento.asc(),
                    ApontamentoProducaoModel.id.asc(),
                )
            ).all()
        )

        total_segundos = Decimal("0")
        ativo_desde: datetime | None = None
        now_utc = datetime.now(UTC)
        for evento in eventos:
            evento_at = self._normalize_datetime(evento.data_hora_evento)
            if evento.evento in {"START", "RETOMADA"}:
                ativo_desde = evento_at
            elif evento.evento in {"PAUSA", "STOP"} and ativo_desde is not None:
                delta = Decimal((evento_at - ativo_desde).total_seconds())
                if delta > 0:
                    total_segundos += delta
                ativo_desde = None

        if ativo_desde is not None:
            delta = Decimal((now_utc - ativo_desde).total_seconds())
            if delta > 0:
                total_segundos += delta

        return total_segundos

    def _snapshot_material_cost(self, snapshot: dict[str, Any]) -> Decimal:
        materiais = snapshot.get("materiais_planejados", [])
        total = Decimal("0")
        for item in materiais:
            try:
                total += Decimal(str(item.get("custo_total", "0")))
            except Exception:  # noqa: BLE001
                continue
        return total

    def _custo_material_real_ordem(self, ordem_id: int) -> Decimal:
        rows = self.db.execute(
            select(EstoqueMovimentacaoModel, EstoqueLoteModel)
            .join(EstoqueLoteModel, EstoqueLoteModel.id == EstoqueMovimentacaoModel.lote_id)
            .where(
                EstoqueMovimentacaoModel.ordem_id == ordem_id,
                EstoqueMovimentacaoModel.tipo_movimento.in_(MOVIMENTOS_CONSUMO),
            )
        ).all()

        total = Decimal("0")
        for mov, lote in rows:
            qtd_inicial = Decimal(lote.quantidade_inicial)
            if qtd_inicial <= 0:
                continue
            custo_unit = Decimal(lote.custo_total) / qtd_inicial
            total += custo_unit * Decimal(mov.quantidade)
        return total

    def _custo_orcado_total_produto(self, produto_final_id: int) -> Decimal | None:
        versao = self.db.scalar(
            select(OrcamentoVersaoModel)
            .join(OrcamentoModel, OrcamentoModel.id == OrcamentoVersaoModel.orcamento_id)
            .where(
                OrcamentoModel.produto_final_id == produto_final_id,
                OrcamentoModel.status != "REJEITADO",
            )
            .order_by(OrcamentoVersaoModel.created_at.desc(), OrcamentoVersaoModel.versao.desc())
            .limit(1)
        )
        if versao is None:
            return None
        return (
            Decimal(versao.custo_material_total)
            + Decimal(versao.custo_maquina_total)
            + Decimal(versao.custo_indireto_total)
        )

    def _resumo_operacoes_ordem(self, ordem_id: int) -> list[dict[str, Any]]:
        op_rows = self.db.execute(
            select(OrdemOperacaoModel, CentroTrabalhoModel)
            .join(
                CentroTrabalhoModel,
                CentroTrabalhoModel.id == OrdemOperacaoModel.centro_trabalho_id,
            )
            .where(OrdemOperacaoModel.ordem_id == ordem_id)
            .order_by(OrdemOperacaoModel.sequencia)
        ).all()

        result: list[dict[str, Any]] = []
        for op, centro in op_rows:
            eventos_count = self.db.scalar(
                select(func.count()).where(ApontamentoProducaoModel.ordem_operacao_id == op.id)
            ) or 0
            refugos_count = self.db.scalar(
                select(func.count()).where(RefugoProducaoModel.ordem_operacao_id == op.id)
            ) or 0
            tempo_horas = self._tempo_real_segundos_operacao(op.id) / Decimal("3600")
            result.append(
                {
                    "ordem_operacao_id": op.id,
                    "sequencia": op.sequencia,
                    "centro_codigo": centro.codigo,
                    "centro_nome": centro.nome,
                    "status": op.status,
                    "quantidade_eventos": int(eventos_count),
                    "quantidade_refugos": int(refugos_count),
                    "tempo_real_horas": tempo_horas,
                }
            )
        return result

    def _movimentacoes_ordem(self, ordem_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(EstoqueMovimentacaoModel, EstoqueLoteModel, InsumoModel)
            .join(EstoqueLoteModel, EstoqueLoteModel.id == EstoqueMovimentacaoModel.lote_id)
            .join(InsumoModel, InsumoModel.id == EstoqueLoteModel.insumo_id)
            .where(EstoqueMovimentacaoModel.ordem_id == ordem_id)
            .order_by(EstoqueMovimentacaoModel.data_hora.asc(), EstoqueMovimentacaoModel.id.asc())
        ).all()

        items: list[dict[str, Any]] = []
        for mov, lote, insumo in rows:
            qtd_inicial = Decimal(lote.quantidade_inicial)
            if qtd_inicial > 0:
                custo_unit = Decimal(lote.custo_total) / qtd_inicial
                custo_aprox = custo_unit * Decimal(mov.quantidade)
            else:
                custo_aprox = Decimal("0")

            items.append(
                {
                    "id": mov.id,
                    "lote_id": mov.lote_id,
                    "codigo_lote": lote.codigo_lote,
                    "insumo_id": insumo.id,
                    "insumo_codigo": insumo.codigo,
                    "insumo_descricao": insumo.descricao,
                    "tipo_movimento": mov.tipo_movimento,
                    "quantidade": mov.quantidade,
                    "custo_aproximado": custo_aprox,
                    "ordem_id": mov.ordem_id,
                    "data_hora": mov.data_hora,
                    "observacao": mov.observacao,
                    "is_retalho": lote.is_retalho,
                    "lote_origem_id": lote.lote_origem_id,
                }
            )
        return items

    def _rastrear_lotes(
        self,
        movimentacoes: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        lote_ids: set[int] = {int(mov["lote_id"]) for mov in movimentacoes}
        loaded_ids: set[int] = set()
        lotes: dict[int, EstoqueLoteModel] = {}

        while lote_ids - loaded_ids:
            current = list(lote_ids - loaded_ids)
            rows = list(
                self.db.scalars(select(EstoqueLoteModel).where(EstoqueLoteModel.id.in_(current))).all()
            )
            for lote in rows:
                lotes[lote.id] = lote
                loaded_ids.add(lote.id)
                if lote.lote_origem_id is not None:
                    lote_ids.add(int(lote.lote_origem_id))

        if not lotes:
            return [], []

        insumo_ids = {lote.insumo_id for lote in lotes.values()}
        insumos = {
            insumo.id: insumo
            for insumo in self.db.scalars(select(InsumoModel).where(InsumoModel.id.in_(insumo_ids))).all()
        }

        lotes_payload = []
        fluxo_retalhos = []
        for lote in sorted(lotes.values(), key=lambda item: item.id):
            insumo = insumos.get(lote.insumo_id)
            if insumo is None:
                continue
            lotes_payload.append(
                {
                    "lote_id": lote.id,
                    "codigo_lote": lote.codigo_lote,
                    "insumo_id": insumo.id,
                    "insumo_codigo": insumo.codigo,
                    "insumo_descricao": insumo.descricao,
                    "quantidade_inicial": lote.quantidade_inicial,
                    "quantidade_disponivel": lote.quantidade_disponivel,
                    "custo_total": lote.custo_total,
                    "is_retalho": lote.is_retalho,
                    "lote_origem_id": lote.lote_origem_id,
                }
            )
            if lote.lote_origem_id is not None:
                fluxo_retalhos.append(
                    {
                        "lote_origem_id": lote.lote_origem_id,
                        "lote_retalho_id": lote.id,
                    }
                )
        return lotes_payload, fluxo_retalhos

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
