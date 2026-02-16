from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from modules.cadastro.infrastructure.models import (
    CentroTrabalhoModel,
    ClienteModel,
    ProdutoFinalModel,
)
from modules.engenharia_bom.application.services import BomService
from modules.engenharia_bom.infrastructure.models import BomModel
from modules.ordens_producao.infrastructure.models import (
    OrdemOperacaoModel,
    OrdemProducaoModel,
)

HTTP_422 = status.HTTP_422_UNPROCESSABLE_CONTENT
STATUS_OP = {
    "ABERTA",
    "PLANEJADA",
    "EM_PRODUCAO",
    "PAUSADA",
    "FINALIZADA",
    "CANCELADA",
}
STATUS_OPERACAO = {"PENDENTE", "EM_EXECUCAO", "PAUSADA", "CONCLUIDA"}
TRANSICOES_STATUS = {
    "ABERTA": {"PLANEJADA", "CANCELADA"},
    "PLANEJADA": {"EM_PRODUCAO", "CANCELADA"},
    "EM_PRODUCAO": {"PAUSADA", "FINALIZADA"},
    "PAUSADA": {"EM_PRODUCAO", "CANCELADA"},
    "FINALIZADA": set(),
    "CANCELADA": set(),
}


class OrdensProducaoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.bom_service = BomService(db)

    def create_ordem(self, payload: dict[str, Any]) -> dict[str, Any]:
        produto = self._ensure_produto_exists(int(payload["produto_final_id"]))
        cliente_id = payload.get("cliente_id")
        if cliente_id is not None:
            self._ensure_cliente_exists(int(cliente_id))

        centro_id = payload.get("centro_trabalho_id")
        if centro_id is not None:
            self._ensure_centro_exists(int(centro_id))

        quantidade_planejada = self._to_decimal(
            payload["quantidade_planejada"],
            "quantidade_planejada",
        )
        if quantidade_planejada <= 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail="quantidade_planejada deve ser maior que zero.",
            )

        prioridade = int(payload.get("prioridade", 3))
        if prioridade < 1 or prioridade > 5:
            raise HTTPException(
                status_code=HTTP_422,
                detail="prioridade deve estar entre 1 e 5.",
            )

        previsao_inicio = payload.get("previsao_inicio")
        previsao_fim = payload.get("previsao_fim")
        if previsao_inicio and previsao_fim and previsao_fim < previsao_inicio:
            raise HTTPException(
                status_code=HTTP_422,
                detail="previsao_fim nao pode ser menor que previsao_inicio.",
            )

        bom = self._resolve_bom(produto_final_id=produto.id, bom_id=payload.get("bom_id"))
        numero_op = (payload.get("numero_op") or self._generate_numero_op()).strip()
        self._ensure_numero_op_unique(numero_op)

        operacoes_payload = payload.get("operacoes", [])
        status_inicial = "PLANEJADA" if operacoes_payload else "ABERTA"
        bom_snapshot = self._build_bom_snapshot(
            bom_id=bom.id,
            quantidade_planejada=quantidade_planejada,
        )

        ordem = OrdemProducaoModel(
            numero_op=numero_op,
            cliente_id=cliente_id,
            produto_final_id=produto.id,
            bom_id=bom.id,
            centro_trabalho_id=centro_id,
            quantidade_planejada=quantidade_planejada,
            quantidade_produzida=Decimal("0"),
            quantidade_refugada=Decimal("0"),
            status=status_inicial,
            prioridade=prioridade,
            previsao_inicio=previsao_inicio,
            previsao_fim=previsao_fim,
            observacao=payload.get("observacao"),
            bom_snapshot_json=self._json_safe(bom_snapshot),
        )
        self.db.add(ordem)
        self.db.flush()

        if operacoes_payload:
            self._add_operacoes_em_lote(ordem_id=ordem.id, operacoes=operacoes_payload)

        self._commit_or_409("Falha ao criar ordem de producao.")
        return self.get_ordem_detail(ordem.id)

    def list_ordens(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        status_filter: str | None = None,
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
        if status_filter:
            if status_filter not in STATUS_OP:
                raise HTTPException(
                    status_code=HTTP_422,
                    detail="status invalido para filtro de OP.",
                )
            stmt = stmt.where(OrdemProducaoModel.status == status_filter)

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = (
            stmt.order_by(OrdemProducaoModel.created_at.desc(), OrdemProducaoModel.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = self.db.execute(stmt).all()

        items = [
            {
                "id": ordem.id,
                "numero_op": ordem.numero_op,
                "status": ordem.status,
                "cliente_id": ordem.cliente_id,
                "cliente_nome": cliente.razao_social if cliente else None,
                "produto_final_id": ordem.produto_final_id,
                "produto_codigo": produto.codigo,
                "produto_descricao": produto.descricao,
                "bom_id": ordem.bom_id,
                "quantidade_planejada": ordem.quantidade_planejada,
                "quantidade_produzida": ordem.quantidade_produzida,
                "quantidade_refugada": ordem.quantidade_refugada,
                "prioridade": ordem.prioridade,
                "data_emissao": ordem.data_emissao,
                "previsao_inicio": ordem.previsao_inicio,
                "previsao_fim": ordem.previsao_fim,
                "created_at": ordem.created_at,
                "updated_at": ordem.updated_at,
            }
            for ordem, produto, cliente in rows
        ]
        return items, int(total)

    def get_ordem_detail(self, ordem_id: int) -> dict[str, Any]:
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
                detail="Ordem de producao nao encontrada.",
            )
        ordem, produto, cliente = row

        operacoes = self._list_operacoes(ordem.id)
        return {
            "id": ordem.id,
            "numero_op": ordem.numero_op,
            "status": ordem.status,
            "cliente_id": ordem.cliente_id,
            "cliente_nome": cliente.razao_social if cliente else None,
            "produto_final_id": ordem.produto_final_id,
            "produto_codigo": produto.codigo,
            "produto_descricao": produto.descricao,
            "bom_id": ordem.bom_id,
            "quantidade_planejada": ordem.quantidade_planejada,
            "quantidade_produzida": ordem.quantidade_produzida,
            "quantidade_refugada": ordem.quantidade_refugada,
            "prioridade": ordem.prioridade,
            "data_emissao": ordem.data_emissao,
            "previsao_inicio": ordem.previsao_inicio,
            "previsao_fim": ordem.previsao_fim,
            "inicio_real": ordem.inicio_real,
            "fim_real": ordem.fim_real,
            "observacao": ordem.observacao,
            "bom_snapshot_json": ordem.bom_snapshot_json or {},
            "created_at": ordem.created_at,
            "updated_at": ordem.updated_at,
            "operacoes": operacoes,
        }

    def add_operacao(self, *, ordem_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        ordem = self._get_ordem_or_404(ordem_id)
        if ordem.status not in {"ABERTA", "PLANEJADA"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Operacoes podem ser adicionadas apenas em OP ABERTA/PLANEJADA.",
            )

        self._add_operacao(ordem_id=ordem.id, payload=payload)
        if ordem.status == "ABERTA":
            ordem.status = "PLANEJADA"
            ordem.updated_at = datetime.now(UTC)

        self._commit_or_409("Falha ao adicionar operacao da OP.")
        return self.get_ordem_detail(ordem.id)

    def update_status(self, *, ordem_id: int, new_status: str) -> dict[str, Any]:
        ordem = self._get_ordem_or_404(ordem_id)
        status_target = self._enum_to_str(new_status)
        if status_target not in STATUS_OP:
            raise HTTPException(
                status_code=HTTP_422,
                detail="status invalido para OP.",
            )

        allowed = TRANSICOES_STATUS.get(ordem.status, set())
        if status_target not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Transicao de status invalida: {ordem.status} -> {status_target}.",
            )

        if status_target == "EM_PRODUCAO" and ordem.inicio_real is None:
            ordem.inicio_real = datetime.now(UTC)
        if status_target in {"FINALIZADA", "CANCELADA"} and ordem.fim_real is None:
            ordem.fim_real = datetime.now(UTC)

        ordem.status = status_target
        ordem.updated_at = datetime.now(UTC)
        self._commit_or_409("Falha ao atualizar status da OP.")
        return self.get_ordem_detail(ordem.id)

    def _add_operacoes_em_lote(self, *, ordem_id: int, operacoes: list[dict[str, Any]]) -> None:
        for payload in operacoes:
            self._add_operacao(ordem_id=ordem_id, payload=payload)

    def _add_operacao(self, *, ordem_id: int, payload: dict[str, Any]) -> OrdemOperacaoModel:
        centro = self._ensure_centro_exists(int(payload["centro_trabalho_id"]))
        sequencia = payload.get("sequencia")
        if sequencia is None:
            sequencia = self._next_sequencia(ordem_id)

        self._ensure_sequencia_disponivel(ordem_id=ordem_id, sequencia=int(sequencia))
        setup_planejado = self._to_decimal(
            payload.get("setup_planejado_min", payload.get("setup_min", centro.setup_padrao_min)),
            "setup_planejado_min",
        )
        ciclo_planejado = self._to_decimal(
            payload.get("ciclo_planejado_min", payload.get("ciclo_min", Decimal("0"))),
            "ciclo_planejado_min",
        )
        if setup_planejado < 0 or ciclo_planejado < 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail="setup/ciclo planejado nao podem ser negativos.",
            )

        status_op = self._enum_to_str(payload.get("status", "PENDENTE"))
        if status_op not in STATUS_OPERACAO:
            raise HTTPException(
                status_code=HTTP_422,
                detail="status invalido para operacao de OP.",
            )

        operacao = OrdemOperacaoModel(
            ordem_id=ordem_id,
            sequencia=int(sequencia),
            centro_trabalho_id=centro.id,
            setup_planejado_min=setup_planejado,
            ciclo_planejado_min=ciclo_planejado,
            status=status_op,
        )
        self.db.add(operacao)
        return operacao

    def _list_operacoes(self, ordem_id: int) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(OrdemOperacaoModel, CentroTrabalhoModel)
            .join(
                CentroTrabalhoModel,
                CentroTrabalhoModel.id == OrdemOperacaoModel.centro_trabalho_id,
            )
            .where(OrdemOperacaoModel.ordem_id == ordem_id)
            .order_by(OrdemOperacaoModel.sequencia, OrdemOperacaoModel.id)
        ).all()
        return [
            {
                "id": op.id,
                "sequencia": op.sequencia,
                "centro_trabalho_id": op.centro_trabalho_id,
                "centro_codigo": centro.codigo,
                "centro_nome": centro.nome,
                "setup_planejado_min": op.setup_planejado_min,
                "ciclo_planejado_min": op.ciclo_planejado_min,
                "status": op.status,
                "created_at": op.created_at,
                "updated_at": op.updated_at,
            }
            for op, centro in rows
        ]

    def _resolve_bom(self, *, produto_final_id: int, bom_id: Any) -> BomModel:
        if bom_id is not None:
            bom = self.db.get(BomModel, int(bom_id))
            if bom is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="BOM nao encontrada.",
                )
            if bom.produto_final_id != produto_final_id:
                raise HTTPException(
                    status_code=HTTP_422,
                    detail="BOM informada nao pertence ao produto da OP.",
                )
            return bom

        status_priority = case(
            (BomModel.status == "ATIVA", 0),
            (BomModel.status == "RASCUNHO", 1),
            (BomModel.status == "OBSOLETA", 2),
            else_=3,
        )
        bom = self.db.scalar(
            select(BomModel)
            .where(BomModel.produto_final_id == produto_final_id)
            .order_by(status_priority, BomModel.versao.desc())
            .limit(1)
        )
        if bom is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Produto sem BOM cadastrada para emissao de OP.",
            )
        return bom

    def _build_bom_snapshot(self, *, bom_id: int, quantidade_planejada: Decimal) -> dict[str, Any]:
        bom = self.bom_service.get_bom_or_404(bom_id)
        _, tree = self.bom_service.build_tree(bom_id)
        _, materiais, _ = self.bom_service.explode_bom(
            bom_id=bom_id,
            quantidade_base=quantidade_planejada,
        )
        return {
            "bom_id": bom.id,
            "produto_final_id": bom.produto_final_id,
            "bom_versao": bom.versao,
            "capturado_em": datetime.now(UTC).isoformat(),
            "quantidade_planejada": quantidade_planejada,
            "tree": tree,
            "materiais_planejados": materiais,
        }

    def _next_sequencia(self, ordem_id: int) -> int:
        max_seq = self.db.scalar(
            select(func.max(OrdemOperacaoModel.sequencia)).where(
                OrdemOperacaoModel.ordem_id == ordem_id
            )
        )
        return int(max_seq or 0) + 1

    def _ensure_sequencia_disponivel(self, *, ordem_id: int, sequencia: int) -> None:
        existing = self.db.scalar(
            select(OrdemOperacaoModel.id).where(
                OrdemOperacaoModel.ordem_id == ordem_id,
                OrdemOperacaoModel.sequencia == sequencia,
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Sequencia de operacao ja cadastrada para esta OP.",
            )

    def _ensure_numero_op_unique(self, numero_op: str) -> None:
        existing_id = self.db.scalar(
            select(OrdemProducaoModel.id).where(OrdemProducaoModel.numero_op == numero_op)
        )
        if existing_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="numero_op ja cadastrado.",
            )

    def _generate_numero_op(self) -> str:
        return f"OP-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')[:16]}"

    def _ensure_produto_exists(self, produto_id: int) -> ProdutoFinalModel:
        produto = self.db.get(ProdutoFinalModel, produto_id)
        if produto is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Produto final nao encontrado.",
            )
        return produto

    def _ensure_cliente_exists(self, cliente_id: int) -> ClienteModel:
        cliente = self.db.get(ClienteModel, cliente_id)
        if cliente is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente nao encontrado.",
            )
        return cliente

    def _ensure_centro_exists(self, centro_id: int) -> CentroTrabalhoModel:
        centro = self.db.get(CentroTrabalhoModel, centro_id)
        if centro is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Centro de trabalho nao encontrado.",
            )
        return centro

    def _get_ordem_or_404(self, ordem_id: int) -> OrdemProducaoModel:
        ordem = self.db.get(OrdemProducaoModel, ordem_id)
        if ordem is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ordem de producao nao encontrada.",
            )
        return ordem

    def _to_decimal(self, value: Any, field_name: str) -> Decimal:
        try:
            return Decimal(str(value))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=HTTP_422,
                detail=f"Valor invalido para {field_name}.",
            ) from exc

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {str(key): self._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        return value

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
            if "ordens_de_producao_numero_op_key" in str(exc.orig):
                detail = "numero_op ja cadastrado."
            if "uq_ordens_operacoes_seq" in str(exc.orig):
                detail = "Sequencia de operacao duplicada para a OP."
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
