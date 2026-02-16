from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from modules.cadastro.infrastructure.models import InsumoModel, ProdutoFinalModel
from modules.engenharia_bom.infrastructure.models import BomItemModel, BomModel

STATUS_RASCUNHO = "RASCUNHO"
STATUS_ATIVA = "ATIVA"
STATUS_OBSOLETA = "OBSOLETA"
STATUS_GRAFO = (STATUS_RASCUNHO, STATUS_ATIVA)

ITEM_TIPO_INSUMO = "INSUMO"
ITEM_TIPO_SUBCONJUNTO = "SUBCONJUNTO"


class BomService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_boms(
        self,
        *,
        page: int,
        page_size: int,
        produto_final_id: int | None = None,
        status_filter: str | None = None,
    ) -> tuple[list[BomModel], int]:
        stmt = select(BomModel)

        if produto_final_id is not None:
            stmt = stmt.where(BomModel.produto_final_id == produto_final_id)

        if status_filter is not None:
            stmt = stmt.where(BomModel.status == status_filter)

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = (
            stmt.order_by(BomModel.produto_final_id, BomModel.versao.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(stmt).all()), total

    def get_bom_or_404(self, bom_id: int) -> BomModel:
        bom = self.db.get(BomModel, bom_id)
        if bom is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="BOM nao encontrada.",
            )
        return bom

    def create_bom(self, payload: dict[str, Any]) -> BomModel:
        produto_final_id = int(payload["produto_final_id"])
        status_value = self._enum_to_str(payload.get("status", STATUS_RASCUNHO))
        valido_de = payload.get("valido_de") or date.today()
        valido_ate = payload.get("valido_ate")
        observacao = payload.get("observacao")

        self._ensure_produto_exists(produto_final_id)
        self._validate_validity_period(valido_de=valido_de, valido_ate=valido_ate)

        next_versao = self._next_version(produto_final_id)
        if status_value == STATUS_ATIVA:
            self._obsoletar_boms_ativas(produto_final_id=produto_final_id, exclude_bom_id=None)

        bom = BomModel(
            produto_final_id=produto_final_id,
            versao=next_versao,
            status=status_value,
            valido_de=valido_de,
            valido_ate=valido_ate,
            observacao=observacao,
        )
        self.db.add(bom)
        self._commit_or_409("Falha ao criar BOM.")
        self.db.refresh(bom)
        return bom

    def update_bom(self, bom_id: int, payload: dict[str, Any]) -> BomModel:
        bom = self.get_bom_or_404(bom_id)
        status_value = self._enum_to_str(payload.get("status", bom.status))
        novo_valido_de = payload.get("valido_de", bom.valido_de)
        novo_valido_ate = payload.get("valido_ate", bom.valido_ate)

        self._validate_validity_period(valido_de=novo_valido_de, valido_ate=novo_valido_ate)

        if status_value == STATUS_ATIVA and bom.status != STATUS_ATIVA:
            self._obsoletar_boms_ativas(produto_final_id=bom.produto_final_id, exclude_bom_id=bom.id)

        if "status" in payload:
            bom.status = status_value
        if "valido_de" in payload:
            bom.valido_de = novo_valido_de
        if "valido_ate" in payload:
            bom.valido_ate = novo_valido_ate
        if "observacao" in payload:
            bom.observacao = payload.get("observacao")

        bom.updated_at = datetime.now(UTC)
        self._commit_or_409("Falha ao atualizar BOM.")
        self.db.refresh(bom)
        return bom

    def create_item(self, bom_id: int, payload: dict[str, Any]) -> BomItemModel:
        bom = self.get_bom_or_404(bom_id)
        self._ensure_bom_editavel(bom)

        normalized = self._normalize_item_payload(
            bom=bom,
            payload=payload,
            current_item_id=None,
            current_parent_item_id=None,
        )
        item = BomItemModel(bom_id=bom_id, **normalized)

        self.db.add(item)
        self._commit_or_409("Falha ao criar item de BOM.")
        self.db.refresh(item)
        return item

    def update_item(self, bom_id: int, item_id: int, payload: dict[str, Any]) -> BomItemModel:
        bom = self.get_bom_or_404(bom_id)
        self._ensure_bom_editavel(bom)
        item = self.get_item_or_404(bom_id=bom_id, item_id=item_id)

        current_data = {
            "parent_item_id": item.parent_item_id,
            "ordem": item.ordem,
            "item_tipo": item.item_tipo,
            "insumo_id": item.insumo_id,
            "produto_filho_id": item.produto_filho_id,
            "quantidade": item.quantidade,
            "unidade_medida": item.unidade_medida,
            "perda_pct": item.perda_pct,
            "observacao": item.observacao,
        }
        merged_payload = {**current_data, **payload}

        normalized = self._normalize_item_payload(
            bom=bom,
            payload=merged_payload,
            current_item_id=item.id,
            current_parent_item_id=item.parent_item_id,
        )

        for field, value in normalized.items():
            setattr(item, field, value)

        item.updated_at = datetime.now(UTC)
        self._commit_or_409("Falha ao atualizar item de BOM.")
        self.db.refresh(item)
        return item

    def delete_item(self, bom_id: int, item_id: int) -> None:
        bom = self.get_bom_or_404(bom_id)
        self._ensure_bom_editavel(bom)
        item = self.get_item_or_404(bom_id=bom_id, item_id=item_id)
        self.db.delete(item)
        self._commit_or_409("Falha ao remover item de BOM.")

    def get_item_or_404(self, *, bom_id: int, item_id: int) -> BomItemModel:
        item = self.db.get(BomItemModel, item_id)
        if item is None or item.bom_id != bom_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item de BOM nao encontrado.",
            )
        return item

    def build_tree(self, bom_id: int) -> tuple[BomModel, list[dict[str, Any]]]:
        bom = self.get_bom_or_404(bom_id)
        item_maps = self._items_by_parent_for_bom(bom_id)
        all_items = [item for item_list in item_maps.values() for item in item_list]

        if not all_items:
            return bom, []

        insumo_ids = {item.insumo_id for item in all_items if item.insumo_id is not None}
        produto_ids = {item.produto_filho_id for item in all_items if item.produto_filho_id is not None}

        insumo_map = self._insumo_map(insumo_ids)
        produto_map = self._produto_map(produto_ids)

        nodes_by_id: dict[int, dict[str, Any]] = {}
        for item in all_items:
            codigo: str | None = None
            descricao: str | None = None

            if item.item_tipo == ITEM_TIPO_INSUMO and item.insumo_id is not None:
                insumo = insumo_map.get(item.insumo_id)
                if insumo is not None:
                    codigo = insumo.codigo
                    descricao = insumo.descricao

            if item.item_tipo == ITEM_TIPO_SUBCONJUNTO and item.produto_filho_id is not None:
                produto = produto_map.get(item.produto_filho_id)
                if produto is not None:
                    codigo = produto.codigo
                    descricao = produto.descricao

            nodes_by_id[item.id] = {
                "id": item.id,
                "parent_item_id": item.parent_item_id,
                "ordem": item.ordem,
                "item_tipo": item.item_tipo,
                "insumo_id": item.insumo_id,
                "produto_filho_id": item.produto_filho_id,
                "codigo": codigo,
                "descricao": descricao,
                "quantidade": item.quantidade,
                "unidade_medida": item.unidade_medida,
                "perda_pct": item.perda_pct,
                "observacao": item.observacao,
                "children": [],
            }

        roots: list[dict[str, Any]] = []
        for node in nodes_by_id.values():
            parent_id = node["parent_item_id"]
            if parent_id is None:
                roots.append(node)
            else:
                parent_node = nodes_by_id.get(parent_id)
                if parent_node is not None:
                    parent_node["children"].append(node)
                else:
                    roots.append(node)

        self._sort_tree(roots)
        return bom, roots

    def explode_bom(
        self,
        *,
        bom_id: int,
        quantidade_base: Decimal,
    ) -> tuple[BomModel, list[dict[str, Any]], Decimal]:
        if quantidade_base <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="quantidade_base deve ser maior que zero.",
            )

        bom = self.get_bom_or_404(bom_id)
        accumulator: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        items_cache: dict[int, dict[int | None, list[BomItemModel]]] = {}
        product_stack = {bom.produto_final_id}

        self._explode_from_parent(
            bom_id=bom.id,
            parent_item_id=None,
            fator=quantidade_base,
            accumulator=accumulator,
            items_cache=items_cache,
            product_stack=product_stack,
        )

        insumo_details, total_custo = self._build_explosion_details(accumulator)
        return bom, insumo_details, total_custo

    def _explode_from_parent(
        self,
        *,
        bom_id: int,
        parent_item_id: int | None,
        fator: Decimal,
        accumulator: dict[int, Decimal],
        items_cache: dict[int, dict[int | None, list[BomItemModel]]],
        product_stack: set[int],
    ) -> None:
        items_by_parent = self._items_by_parent_for_bom(bom_id=bom_id, cache=items_cache)
        for item in items_by_parent.get(parent_item_id, []):
            perda_factor = Decimal("1") + (Decimal(item.perda_pct) / Decimal("100"))
            fator_item = Decimal(fator) * Decimal(item.quantidade) * perda_factor

            if item.item_tipo == ITEM_TIPO_INSUMO and item.insumo_id is not None:
                accumulator[item.insumo_id] += fator_item
                continue

            if item.item_tipo != ITEM_TIPO_SUBCONJUNTO or item.produto_filho_id is None:
                continue

            nested_children = items_by_parent.get(item.id, [])
            if nested_children:
                self._ensure_no_runtime_cycle(product_stack, item.produto_filho_id)
                product_stack.add(item.produto_filho_id)
                self._explode_from_parent(
                    bom_id=bom_id,
                    parent_item_id=item.id,
                    fator=fator_item,
                    accumulator=accumulator,
                    items_cache=items_cache,
                    product_stack=product_stack,
                )
                product_stack.remove(item.produto_filho_id)
                continue

            child_bom = self._select_bom_para_explodir(item.produto_filho_id)
            if child_bom is None:
                continue

            self._ensure_no_runtime_cycle(product_stack, item.produto_filho_id)
            product_stack.add(item.produto_filho_id)
            self._explode_from_parent(
                bom_id=child_bom.id,
                parent_item_id=None,
                fator=fator_item,
                accumulator=accumulator,
                items_cache=items_cache,
                product_stack=product_stack,
            )
            product_stack.remove(item.produto_filho_id)

    def _build_explosion_details(
        self, accumulator: dict[int, Decimal]
    ) -> tuple[list[dict[str, Any]], Decimal]:
        if not accumulator:
            return [], Decimal("0")

        insumo_map = self._insumo_map(set(accumulator.keys()))
        result: list[dict[str, Any]] = []
        custo_total = Decimal("0")

        ordered_insumos = sorted(
            (insumo_map[insumo_id] for insumo_id in accumulator if insumo_id in insumo_map),
            key=lambda item: item.codigo,
        )

        for insumo in ordered_insumos:
            quantidade_total = accumulator[insumo.id]
            custo_unitario = Decimal(insumo.custo_unitario)
            custo_item = quantidade_total * custo_unitario
            custo_total += custo_item

            result.append(
                {
                    "insumo_id": insumo.id,
                    "codigo": insumo.codigo,
                    "descricao": insumo.descricao,
                    "unidade_medida": insumo.unidade_medida,
                    "quantidade_total": quantidade_total,
                    "custo_unitario": custo_unitario,
                    "custo_total": custo_item,
                }
            )

        return result, custo_total

    def _normalize_item_payload(
        self,
        *,
        bom: BomModel,
        payload: dict[str, Any],
        current_item_id: int | None,
        current_parent_item_id: int | None,
    ) -> dict[str, Any]:
        item_tipo = self._enum_to_str(payload.get("item_tipo"))
        if item_tipo not in (ITEM_TIPO_INSUMO, ITEM_TIPO_SUBCONJUNTO):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="item_tipo invalido para item de BOM.",
            )

        parent_item_id = payload.get("parent_item_id")
        if current_item_id is not None and "parent_item_id" not in payload:
            parent_item_id = current_parent_item_id
        parent_item = self._validate_parent_item(
            bom_id=bom.id,
            parent_item_id=parent_item_id,
            current_item_id=current_item_id,
        )
        self._ensure_parent_not_descendant(
            bom_id=bom.id,
            current_item_id=current_item_id,
            parent_item_id=parent_item_id,
        )

        ordem = int(payload.get("ordem", 1))
        quantidade = Decimal(payload.get("quantidade"))
        perda_pct = Decimal(payload.get("perda_pct", Decimal("0")))
        observacao = payload.get("observacao")

        if quantidade <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="quantidade deve ser maior que zero.",
            )
        if perda_pct < 0 or perda_pct > 100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="perda_pct deve estar entre 0 e 100.",
            )

        if item_tipo == ITEM_TIPO_INSUMO:
            insumo_id = payload.get("insumo_id")
            produto_filho_id = payload.get("produto_filho_id")
            if insumo_id is None or produto_filho_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Item INSUMO exige insumo_id e proibe produto_filho_id.",
                )
            insumo = self._ensure_insumo_exists(int(insumo_id))
            unidade_medida = self._resolve_unidade_medida(
                informada=payload.get("unidade_medida"),
                referencia=insumo.unidade_medida,
            )
            return {
                "parent_item_id": parent_item_id,
                "ordem": ordem,
                "item_tipo": item_tipo,
                "insumo_id": int(insumo_id),
                "produto_filho_id": None,
                "quantidade": quantidade,
                "unidade_medida": unidade_medida,
                "perda_pct": perda_pct,
                "observacao": observacao,
            }

        insumo_id = payload.get("insumo_id")
        produto_filho_id = payload.get("produto_filho_id")
        if produto_filho_id is None or insumo_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Item SUBCONJUNTO exige produto_filho_id e proibe insumo_id.",
            )

        produto_filho = self._ensure_produto_exists(int(produto_filho_id))
        parent_product_id = bom.produto_final_id
        if parent_item is not None and parent_item.produto_filho_id is not None:
            parent_product_id = int(parent_item.produto_filho_id)

        self._validate_no_cycle(
            parent_product_id=parent_product_id,
            child_product_id=int(produto_filho_id),
            exclude_item_id=current_item_id,
        )

        unidade_medida = self._resolve_unidade_medida(
            informada=payload.get("unidade_medida"),
            referencia=produto_filho.unidade_medida,
        )
        return {
            "parent_item_id": parent_item_id,
            "ordem": ordem,
            "item_tipo": item_tipo,
            "insumo_id": None,
            "produto_filho_id": int(produto_filho_id),
            "quantidade": quantidade,
            "unidade_medida": unidade_medida,
            "perda_pct": perda_pct,
            "observacao": observacao,
        }

    def _validate_parent_item(
        self,
        *,
        bom_id: int,
        parent_item_id: int | None,
        current_item_id: int | None,
    ) -> BomItemModel | None:
        if parent_item_id is None:
            return None

        parent_item = self.db.get(BomItemModel, parent_item_id)
        if parent_item is None or parent_item.bom_id != bom_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="parent_item_id deve referenciar item do mesmo BOM.",
            )
        if current_item_id is not None and parent_item.id == current_item_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Um item nao pode ser pai de si mesmo.",
            )
        if parent_item.item_tipo != ITEM_TIPO_SUBCONJUNTO:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Apenas itens SUBCONJUNTO podem receber filhos.",
            )
        return parent_item

    def _ensure_parent_not_descendant(
        self,
        *,
        bom_id: int,
        current_item_id: int | None,
        parent_item_id: int | None,
    ) -> None:
        if current_item_id is None or parent_item_id is None:
            return

        cursor = parent_item_id
        visited: set[int] = set()
        while cursor is not None:
            if cursor == current_item_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Estrutura de arvore invalida: ciclo por parent_item_id.",
                )
            if cursor in visited:
                break
            visited.add(cursor)

            item = self.db.get(BomItemModel, cursor)
            if item is None or item.bom_id != bom_id:
                break
            cursor = item.parent_item_id

    def _validate_no_cycle(
        self,
        *,
        parent_product_id: int,
        child_product_id: int,
        exclude_item_id: int | None,
    ) -> None:
        if parent_product_id == child_product_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Ciclo detectado: produto nao pode depender de si mesmo.",
            )

        if self._has_product_path(
            start_product_id=child_product_id,
            target_product_id=parent_product_id,
            visited=set(),
            exclude_item_id=exclude_item_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Ciclo detectado na estrutura BOM (A -> ... -> A).",
            )

    def _has_product_path(
        self,
        *,
        start_product_id: int,
        target_product_id: int,
        visited: set[int],
        exclude_item_id: int | None,
    ) -> bool:
        if start_product_id == target_product_id:
            return True

        if start_product_id in visited:
            return False
        visited.add(start_product_id)

        for child_id in self._direct_children_products(
            produto_id=start_product_id,
            exclude_item_id=exclude_item_id,
        ):
            if self._has_product_path(
                start_product_id=child_id,
                target_product_id=target_product_id,
                visited=visited,
                exclude_item_id=exclude_item_id,
            ):
                return True

        return False

    def _direct_children_products(
        self, *, produto_id: int, exclude_item_id: int | None
    ) -> set[int]:
        stmt_top = (
            select(BomItemModel.produto_filho_id)
            .join(BomModel, BomModel.id == BomItemModel.bom_id)
            .where(
                BomModel.status.in_(STATUS_GRAFO),
                BomModel.produto_final_id == produto_id,
                BomItemModel.item_tipo == ITEM_TIPO_SUBCONJUNTO,
                BomItemModel.produto_filho_id.is_not(None),
                BomItemModel.parent_item_id.is_(None),
            )
        )
        if exclude_item_id is not None:
            stmt_top = stmt_top.where(BomItemModel.id != exclude_item_id)

        parent_item = aliased(BomItemModel)
        stmt_nested = (
            select(BomItemModel.produto_filho_id)
            .join(parent_item, parent_item.id == BomItemModel.parent_item_id)
            .join(BomModel, BomModel.id == BomItemModel.bom_id)
            .where(
                BomModel.status.in_(STATUS_GRAFO),
                BomItemModel.item_tipo == ITEM_TIPO_SUBCONJUNTO,
                BomItemModel.produto_filho_id.is_not(None),
                parent_item.item_tipo == ITEM_TIPO_SUBCONJUNTO,
                parent_item.produto_filho_id == produto_id,
            )
        )
        if exclude_item_id is not None:
            stmt_nested = stmt_nested.where(BomItemModel.id != exclude_item_id)

        children: set[int] = set()
        for child_id in self.db.scalars(stmt_top).all():
            if child_id is not None:
                children.add(int(child_id))
        for child_id in self.db.scalars(stmt_nested).all():
            if child_id is not None:
                children.add(int(child_id))

        return children

    def _items_by_parent_for_bom(
        self,
        bom_id: int,
        cache: dict[int, dict[int | None, list[BomItemModel]]] | None = None,
    ) -> dict[int | None, list[BomItemModel]]:
        if cache is not None and bom_id in cache:
            return cache[bom_id]

        stmt = (
            select(BomItemModel)
            .where(BomItemModel.bom_id == bom_id)
            .order_by(BomItemModel.parent_item_id, BomItemModel.ordem, BomItemModel.id)
        )
        items = list(self.db.scalars(stmt).all())
        grouped: dict[int | None, list[BomItemModel]] = defaultdict(list)
        for item in items:
            grouped[item.parent_item_id].append(item)

        if cache is not None:
            cache[bom_id] = grouped
        return grouped

    def _select_bom_para_explodir(self, produto_final_id: int) -> BomModel | None:
        status_priority = case(
            (BomModel.status == STATUS_ATIVA, 0),
            (BomModel.status == STATUS_RASCUNHO, 1),
            else_=2,
        )
        stmt = (
            select(BomModel)
            .where(
                BomModel.produto_final_id == produto_final_id,
                BomModel.status.in_(STATUS_GRAFO),
            )
            .order_by(status_priority, BomModel.versao.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def _insumo_map(self, insumo_ids: set[int]) -> dict[int, InsumoModel]:
        if not insumo_ids:
            return {}
        stmt = select(InsumoModel).where(InsumoModel.id.in_(insumo_ids))
        return {insumo.id: insumo for insumo in self.db.scalars(stmt).all()}

    def _produto_map(self, produto_ids: set[int]) -> dict[int, ProdutoFinalModel]:
        if not produto_ids:
            return {}
        stmt = select(ProdutoFinalModel).where(ProdutoFinalModel.id.in_(produto_ids))
        return {produto.id: produto for produto in self.db.scalars(stmt).all()}

    def _ensure_insumo_exists(self, insumo_id: int) -> InsumoModel:
        insumo = self.db.get(InsumoModel, insumo_id)
        if insumo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Insumo nao encontrado.",
            )
        return insumo

    def _ensure_produto_exists(self, produto_id: int) -> ProdutoFinalModel:
        produto = self.db.get(ProdutoFinalModel, produto_id)
        if produto is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Produto final nao encontrado.",
            )
        return produto

    def _resolve_unidade_medida(self, *, informada: Any, referencia: str) -> str:
        unidade_informada = self._enum_to_str(informada) if informada is not None else None
        if unidade_informada is None:
            return referencia
        if unidade_informada != referencia:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="unidade_medida divergente da referencia do cadastro.",
            )
        return unidade_informada

    def _ensure_bom_editavel(self, bom: BomModel) -> None:
        if bom.status != STATUS_RASCUNHO:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Somente BOM em status RASCUNHO pode ser alterada.",
            )

    def _validate_validity_period(self, *, valido_de: date, valido_ate: date | None) -> None:
        if valido_ate is not None and valido_ate < valido_de:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="valido_ate nao pode ser menor que valido_de.",
            )

    def _next_version(self, produto_final_id: int) -> int:
        current_max = self.db.scalar(
            select(func.max(BomModel.versao)).where(BomModel.produto_final_id == produto_final_id)
        )
        return int(current_max or 0) + 1

    def _obsoletar_boms_ativas(self, *, produto_final_id: int, exclude_bom_id: int | None) -> None:
        stmt = select(BomModel).where(
            BomModel.produto_final_id == produto_final_id,
            BomModel.status == STATUS_ATIVA,
        )
        if exclude_bom_id is not None:
            stmt = stmt.where(BomModel.id != exclude_bom_id)

        for active_bom in self.db.scalars(stmt).all():
            active_bom.status = STATUS_OBSOLETA
            active_bom.updated_at = datetime.now(UTC)

    def _ensure_no_runtime_cycle(self, product_stack: set[int], child_product_id: int) -> None:
        if child_product_id in product_stack:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Ciclo detectado durante explosao da BOM.",
            )

    def _enum_to_str(self, value: Any) -> str:
        if isinstance(value, Enum):
            return str(value.value)
        return str(value)

    def _sort_tree(self, nodes: list[dict[str, Any]]) -> None:
        nodes.sort(key=lambda node: (node["ordem"], node["id"]))
        for node in nodes:
            self._sort_tree(node["children"])

    def _commit_or_409(self, message: str) -> None:
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            detail = message
            if "uq_bom_produto_versao" in str(exc.orig):
                detail = "Versao de BOM duplicada para o mesmo produto."
            if "duplicate key value violates unique constraint" in str(exc.orig):
                detail = "Violacao de unicidade ao persistir BOM."
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
