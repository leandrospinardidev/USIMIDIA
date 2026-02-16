from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

try:
    from pypdf import PdfReader
except Exception:  # noqa: BLE001
    PdfReader = None

from core.config import get_settings
from modules.cadastro.infrastructure.models import (
    CentroTrabalhoModel,
    ClienteModel,
    ProdutoFinalModel,
)
from modules.engenharia_bom.application.services import BomService
from modules.engenharia_bom.infrastructure.models import BomModel
from modules.mes_apontamentos.infrastructure.models import ApontamentoProducaoModel
from modules.orcamentos.infrastructure.models import (
    OrcamentoAnexoModel,
    OrcamentoModel,
    OrcamentoPresetCncHistoricoModel,
    OrcamentoPresetCncModel,
    OrcamentoVersaoModel,
    OrcamentoVersaoOperacaoModel,
)
from modules.ordens_producao.infrastructure.models import OrdemOperacaoModel, OrdemProducaoModel

HTTP_422 = status.HTTP_422_UNPROCESSABLE_CONTENT
STATUS_PERMITIDOS = {"RASCUNHO", "ENVIADO", "APROVADO", "REJEITADO"}
ALLOWED_ANEXO_EXTENSIONS = {
    ".pdf",
    ".dxf",
    ".dwg",
    ".step",
    ".stp",
    ".iges",
    ".igs",
    ".png",
    ".jpg",
    ".jpeg",
}
MAX_ANEXO_SIZE_BYTES = 25 * 1024 * 1024
MATERIAL_PRECO_KG: dict[str, Decimal] = {
    "ACO CARBONO": Decimal("9.50"),
    "ACO INOX": Decimal("24.00"),
    "ALUMINIO": Decimal("21.00"),
    "LATON": Decimal("38.00"),
    "BRONZE": Decimal("45.00"),
    "FOFO NODULAR": Decimal("12.00"),
    "FOFO GG20": Decimal("11.00"),
}
MATERIAL_DENSIDADE_G_CM3: dict[str, Decimal] = {
    "ACO CARBONO": Decimal("7.85"),
    "ACO INOX": Decimal("7.90"),
    "ALUMINIO": Decimal("2.70"),
    "LATON": Decimal("8.50"),
    "BRONZE": Decimal("8.80"),
    "FOFO NODULAR": Decimal("7.20"),
    "FOFO GG20": Decimal("7.10"),
}
RE_DIM_X = re.compile(r"(\d{1,5}(?:[.,]\d+)?)\s*[xX]\s*(\d{1,5}(?:[.,]\d+)?)")
RE_DIAMETRO = re.compile(r"(?:Ø|DIAMETRO|DIA)[\s:]*([0-9]{1,4}(?:[.,][0-9]+)?)")
RE_H7 = re.compile(r"([0-9]{1,4}(?:[.,][0-9]+)?)\s*H[0-9]{1,2}")
RE_QUANTIDADE = re.compile(r"(?:QTD|QTDE|QUANTIDADE)[\s:=]+([0-9]{1,4})")
USO_EVENTOS_COM_ORCAMENTO = {"ORCAMENTO_CRIADO", "ORCAMENTO_APROVADO"}


class OrcamentosService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.bom_service = BomService(db)

    def simulate(self, payload: dict[str, Any]) -> dict[str, Any]:
        produto = self._ensure_produto_exists(int(payload["produto_final_id"]))
        if payload.get("cliente_id") is not None:
            self._ensure_cliente_exists(int(payload["cliente_id"]))

        quantidade = self._to_decimal(payload["quantidade"], "quantidade")
        if quantidade <= 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail="quantidade deve ser maior que zero.",
            )

        margem_lucro_pct = self._to_decimal(
            payload.get("margem_lucro_pct", produto.margem_lucro_padrao_pct),
            "margem_lucro_pct",
        )
        custo_indireto_fixo = self._to_decimal(
            payload.get("custo_indireto_fixo", Decimal("0")),
            "custo_indireto_fixo",
        )
        custo_indireto_pct = self._to_decimal(
            payload.get("custo_indireto_pct", Decimal("0")),
            "custo_indireto_pct",
        )
        self._validate_non_negative("margem_lucro_pct", margem_lucro_pct)
        self._validate_non_negative("custo_indireto_fixo", custo_indireto_fixo)
        self._validate_non_negative("custo_indireto_pct", custo_indireto_pct)

        bom = self._resolve_bom(
            produto_final_id=produto.id,
            bom_id=payload.get("bom_id"),
        )

        _, materiais, custo_material_total = self.bom_service.explode_bom(
            bom_id=bom.id,
            quantidade_base=quantidade,
        )
        operacoes = self._simulate_operacoes(
            operacoes_input=payload.get("operacoes", []),
            quantidade=quantidade,
        )
        custo_maquina_total = sum(
            (Decimal(op["custo_operacao"]) for op in operacoes),
            start=Decimal("0"),
        )
        custo_indireto_total = custo_indireto_fixo + (
            (custo_material_total + custo_maquina_total) * (custo_indireto_pct / Decimal("100"))
        )
        custo_total = custo_material_total + custo_maquina_total + custo_indireto_total
        preco_venda = custo_total * (Decimal("1") + (margem_lucro_pct / Decimal("100")))

        return {
            "produto_final_id": produto.id,
            "bom_id": bom.id,
            "quantidade": quantidade,
            "margem_lucro_pct": margem_lucro_pct,
            "custo_material_total": custo_material_total,
            "custo_maquina_total": custo_maquina_total,
            "custo_indireto_total": custo_indireto_total,
            "custo_total": custo_total,
            "preco_venda": preco_venda,
            "materiais": materiais,
            "operacoes": operacoes,
        }

    def simulate_from_pdf(
        self,
        *,
        centro_trabalho_id: int,
        file_name: str,
        file_bytes: bytes,
        margem_lucro_pct: str | None,
        custo_indireto_fixo: str | None,
        custo_indireto_pct: str | None,
        quantidade_override: int | None,
    ) -> dict[str, Any]:
        if Path(file_name).suffix.lower() != ".pdf":
            raise HTTPException(
                status_code=HTTP_422,
                detail="Para simulacao automatica, envie um arquivo PDF de desenho tecnico.",
            )
        if not file_bytes:
            raise HTTPException(
                status_code=HTTP_422,
                detail="Arquivo PDF vazio.",
            )
        if len(file_bytes) > MAX_ANEXO_SIZE_BYTES:
            raise HTTPException(
                status_code=HTTP_422,
                detail="Arquivo PDF excede o limite de 25MB.",
            )

        centro = self._ensure_centro_exists(centro_trabalho_id)
        margem = self._to_decimal(margem_lucro_pct or "30", "margem_lucro_pct")
        custo_ind_fixo = self._to_decimal(custo_indireto_fixo or "0", "custo_indireto_fixo")
        custo_ind_pct = self._to_decimal(custo_indireto_pct or "0", "custo_indireto_pct")
        self._validate_non_negative("margem_lucro_pct", margem)
        self._validate_non_negative("custo_indireto_fixo", custo_ind_fixo)
        self._validate_non_negative("custo_indireto_pct", custo_ind_pct)
        if quantidade_override is not None and quantidade_override <= 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail="quantidade_override deve ser maior que zero.",
            )

        texto_extraido = self._extract_pdf_text(file_bytes)
        inferencia = self._infer_pdf_desenho(
            texto_extraido,
            quantidade_override=quantidade_override,
        )

        custo_material_unitario = self._estimate_material_unit_cost(inferencia)
        quantidade = Decimal(inferencia["quantidade_considerada"])
        custo_material_total = custo_material_unitario * quantidade

        horas_maquina_unit = self._estimate_machine_hours_unit(
            inferencia=inferencia,
            setup_padrao_min=Decimal(centro.setup_padrao_min or 0),
        )
        taxa_horaria = Decimal(centro.taxa_horaria)
        custo_maquina_total = horas_maquina_unit * taxa_horaria * quantidade
        custo_indireto_total = custo_ind_fixo + (
            (custo_material_total + custo_maquina_total) * (custo_ind_pct / Decimal("100"))
        )
        custo_total = custo_material_total + custo_maquina_total + custo_indireto_total
        preco_venda = custo_total * (Decimal("1") + (margem / Decimal("100")))

        return {
            "leitura": {
                "material_inferido": inferencia["material_inferido"],
                "quantidade_inferida": inferencia["quantidade_inferida"],
                "quantidade_considerada": inferencia["quantidade_considerada"],
                "diametros_mm": inferencia["diametros_mm"],
                "comprimento_mm": inferencia["comprimento_mm"],
                "confianca": inferencia["confianca"],
                "texto_resumo": inferencia["texto_resumo"],
            },
            "custos": {
                "centro_trabalho_id": centro.id,
                "centro_codigo": centro.codigo,
                "centro_nome": centro.nome,
                "taxa_horaria": taxa_horaria,
                "horas_maquina_estimadas_unit": horas_maquina_unit,
                "custo_material_unitario": custo_material_unitario,
                "custo_material_total": custo_material_total,
                "custo_maquina_total": custo_maquina_total,
                "custo_indireto_total": custo_indireto_total,
                "custo_total": custo_total,
                "margem_lucro_pct": margem,
                "preco_venda_sugerido": preco_venda,
            },
            "premissas": inferencia["premissas"],
        }

    def create_orcamento(self, payload: dict[str, Any]) -> dict[str, Any]:
        sim = self.simulate(payload)
        codigo = (payload.get("codigo") or self._generate_codigo()).strip()
        self._ensure_codigo_orcamento_unique(codigo)

        orcamento = OrcamentoModel(
            codigo=codigo,
            cliente_id=payload.get("cliente_id"),
            produto_final_id=sim["produto_final_id"],
            status="RASCUNHO",
            referencia_projeto=payload.get("referencia_projeto"),
            observacao=payload.get("observacao"),
        )
        self.db.add(orcamento)
        self.db.flush()

        self._create_versao(
            orcamento_id=orcamento.id,
            versao=1,
            sim=sim,
            moeda=self._normalize_moeda(payload.get("moeda", "BRL")),
            payload=payload,
        )
        if payload.get("preset_cnc_id") is not None:
            self._aplicar_registro_uso_preset(
                preset_id=int(payload["preset_cnc_id"]),
                tipo_evento="ORCAMENTO_CRIADO",
                erro_previsao_pct=None,
                observacao="Vinculo automatico ao criar orcamento.",
            )
        self._commit_or_409("Falha ao criar orcamento.")
        return self.get_orcamento_detail(orcamento.id)

    def create_nova_versao(self, *, orcamento_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        orcamento = self._get_orcamento_or_404(orcamento_id)

        sim_payload = {
            "cliente_id": orcamento.cliente_id,
            "produto_final_id": orcamento.produto_final_id,
            **payload,
        }
        if (
            "produto_final_id" in payload
            and int(payload["produto_final_id"]) != orcamento.produto_final_id
        ):
            raise HTTPException(
                status_code=HTTP_422,
                detail="produto_final_id da versao deve ser igual ao do orcamento.",
            )

        sim = self.simulate(sim_payload)
        nova_versao = self._next_versao(orcamento.id)
        self._create_versao(
            orcamento_id=orcamento.id,
            versao=nova_versao,
            sim=sim,
            moeda=self._normalize_moeda(payload.get("moeda", "BRL")),
            payload=sim_payload,
        )
        if payload.get("preset_cnc_id") is not None:
            self._aplicar_registro_uso_preset(
                preset_id=int(payload["preset_cnc_id"]),
                tipo_evento="ORCAMENTO_CRIADO",
                erro_previsao_pct=None,
                observacao=f"Vinculo automatico em nova versao {nova_versao}.",
            )
        if payload.get("referencia_projeto") is not None:
            orcamento.referencia_projeto = payload.get("referencia_projeto")
        if payload.get("observacao") is not None:
            orcamento.observacao = payload.get("observacao")
        orcamento.updated_at = datetime.now(UTC)

        self._commit_or_409("Falha ao criar nova versao do orcamento.")
        return self.get_orcamento_detail(orcamento.id)

    def update_status(self, *, orcamento_id: int, status_value: str) -> dict[str, Any]:
        orcamento = self._get_orcamento_or_404(orcamento_id)
        normalized = self._enum_to_str(status_value)
        if normalized not in STATUS_PERMITIDOS:
            raise HTTPException(
                status_code=HTTP_422,
                detail="status invalido para orcamento.",
            )
        orcamento.status = normalized
        orcamento.updated_at = datetime.now(UTC)
        self._commit_or_409("Falha ao atualizar status do orcamento.")
        return self.get_orcamento_detail(orcamento.id)

    def list_orcamentos(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        status_filter: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = (
            select(OrcamentoModel, ProdutoFinalModel, ClienteModel)
            .join(
                ProdutoFinalModel,
                ProdutoFinalModel.id == OrcamentoModel.produto_final_id,
            )
            .join(
                ClienteModel,
                ClienteModel.id == OrcamentoModel.cliente_id,
                isouter=True,
            )
        )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    OrcamentoModel.codigo.ilike(pattern),
                    ProdutoFinalModel.codigo.ilike(pattern),
                    ProdutoFinalModel.descricao.ilike(pattern),
                    ClienteModel.razao_social.ilike(pattern),
                )
            )
        if status_filter:
            stmt = stmt.where(OrcamentoModel.status == status_filter)

        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = (
            stmt.order_by(OrcamentoModel.created_at.desc(), OrcamentoModel.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = self.db.execute(stmt).all()

        latest_map = self._latest_versions_for([orc.id for orc, _, _ in rows])
        items = []
        for orc, produto, cliente in rows:
            versao_atual = latest_map.get(orc.id)
            items.append(
                {
                    "id": orc.id,
                    "codigo": orc.codigo,
                    "status": orc.status,
                    "cliente_id": orc.cliente_id,
                    "cliente_nome": cliente.razao_social if cliente else None,
                    "produto_final_id": orc.produto_final_id,
                    "produto_codigo": produto.codigo,
                    "produto_descricao": produto.descricao,
                    "referencia_projeto": orc.referencia_projeto,
                    "versao_atual": versao_atual["versao"] if versao_atual else None,
                    "preco_venda_atual": versao_atual["preco_venda"] if versao_atual else None,
                    "created_at": orc.created_at,
                    "updated_at": orc.updated_at,
                }
            )
        return items, int(total)

    def get_orcamento_detail(self, orcamento_id: int) -> dict[str, Any]:
        row = self.db.execute(
            select(OrcamentoModel, ProdutoFinalModel, ClienteModel)
            .join(
                ProdutoFinalModel,
                ProdutoFinalModel.id == OrcamentoModel.produto_final_id,
            )
            .join(
                ClienteModel,
                ClienteModel.id == OrcamentoModel.cliente_id,
                isouter=True,
            )
            .where(OrcamentoModel.id == orcamento_id)
        ).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Orcamento nao encontrado.",
            )
        orc, produto, cliente = row

        versoes = list(
            self.db.scalars(
                select(OrcamentoVersaoModel)
                .where(OrcamentoVersaoModel.orcamento_id == orc.id)
                .order_by(OrcamentoVersaoModel.versao.desc())
            ).all()
        )
        anexos = list(
            self.db.scalars(
                select(OrcamentoAnexoModel)
                .where(OrcamentoAnexoModel.orcamento_id == orc.id)
                .order_by(OrcamentoAnexoModel.uploaded_at.desc(), OrcamentoAnexoModel.id.desc())
            ).all()
        )
        versao_ids = [versao.id for versao in versoes]
        ops_map = self._operacoes_por_versao(versao_ids)

        versoes_payload = [
            {
                "id": versao.id,
                "versao": versao.versao,
                "bom_id": versao.bom_id,
                "quantidade": versao.quantidade,
                "margem_lucro_pct": versao.margem_lucro_pct,
                "custo_material_total": versao.custo_material_total,
                "custo_maquina_total": versao.custo_maquina_total,
                "custo_indireto_total": versao.custo_indireto_total,
                "preco_venda": versao.preco_venda,
                "moeda": versao.moeda,
                "created_at": versao.created_at,
                "materiais": (versao.detalhes_json or {}).get("materiais", []),
                "operacoes": ops_map.get(versao.id, []),
            }
            for versao in versoes
        ]

        return {
            "id": orc.id,
            "codigo": orc.codigo,
            "status": orc.status,
            "cliente_id": orc.cliente_id,
            "cliente_nome": cliente.razao_social if cliente else None,
            "produto_final_id": orc.produto_final_id,
            "produto_codigo": produto.codigo,
            "produto_descricao": produto.descricao,
            "referencia_projeto": orc.referencia_projeto,
            "observacao": orc.observacao,
            "created_at": orc.created_at,
            "updated_at": orc.updated_at,
            "versoes": versoes_payload,
            "anexos": [self._anexo_to_payload(anexo) for anexo in anexos],
        }

    def upload_anexo(
        self,
        *,
        orcamento_id: int,
        nome_arquivo: str,
        content_type: str | None,
        observacao: str | None,
        file_bytes: bytes,
    ) -> dict[str, Any]:
        self._get_orcamento_or_404(orcamento_id)
        nome_arquivo_limpo = Path(nome_arquivo).name.strip()
        if not nome_arquivo_limpo:
            raise HTTPException(
                status_code=HTTP_422,
                detail="Nome de arquivo invalido.",
            )
        extensao = Path(nome_arquivo_limpo).suffix.lower()
        if extensao not in ALLOWED_ANEXO_EXTENSIONS:
            raise HTTPException(
                status_code=HTTP_422,
                detail="Extensao de arquivo nao suportada para anexo tecnico.",
            )
        if not file_bytes:
            raise HTTPException(
                status_code=HTTP_422,
                detail="Arquivo vazio nao pode ser enviado.",
            )
        if len(file_bytes) > MAX_ANEXO_SIZE_BYTES:
            raise HTTPException(
                status_code=HTTP_422,
                detail="Arquivo excede o limite de 25MB.",
            )

        storage_filename = f"{uuid.uuid4().hex}{extensao}"
        target_dir = self._upload_root_path() / "orcamentos" / str(orcamento_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        absolute_path = target_dir / storage_filename
        absolute_path.write_bytes(file_bytes)

        relative_path = str(Path("orcamentos") / str(orcamento_id) / storage_filename)
        anexo = OrcamentoAnexoModel(
            orcamento_id=orcamento_id,
            nome_arquivo_original=nome_arquivo_limpo,
            nome_arquivo_storage=storage_filename,
            content_type=content_type,
            tamanho_bytes=len(file_bytes),
            caminho_relativo=relative_path,
            observacao=observacao,
        )
        self.db.add(anexo)
        self._commit_or_409("Falha ao salvar anexo tecnico do orcamento.")
        self.db.refresh(anexo)
        return self._anexo_to_payload(anexo)

    def list_anexos(
        self,
        *,
        orcamento_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        self._get_orcamento_or_404(orcamento_id)
        stmt = select(OrcamentoAnexoModel).where(OrcamentoAnexoModel.orcamento_id == orcamento_id)
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = list(
            self.db.scalars(
                stmt.order_by(OrcamentoAnexoModel.uploaded_at.desc(), OrcamentoAnexoModel.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return [self._anexo_to_payload(row) for row in rows], int(total)

    def get_anexo_download(self, anexo_id: int) -> dict[str, Any]:
        anexo = self.db.get(OrcamentoAnexoModel, anexo_id)
        if anexo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Anexo de orcamento nao encontrado.",
            )
        absolute_path = self._upload_root_path() / anexo.caminho_relativo
        if not absolute_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Arquivo fisico do anexo nao encontrado.",
            )
        return {
            **self._anexo_to_payload(anexo),
            "absolute_path": str(absolute_path),
        }

    def list_presets_cnc(
        self,
        *,
        page: int,
        page_size: int,
        ativo: bool | None = True,
        cliente_id: int | None = None,
        produto_final_id: int | None = None,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        stmt = select(OrcamentoPresetCncModel)
        if ativo is not None:
            stmt = stmt.where(OrcamentoPresetCncModel.ativo == ativo)
        if cliente_id is not None:
            stmt = stmt.where(
                or_(
                    OrcamentoPresetCncModel.cliente_id.is_(None),
                    OrcamentoPresetCncModel.cliente_id == cliente_id,
                )
            )
        if produto_final_id is not None:
            stmt = stmt.where(
                or_(
                    OrcamentoPresetCncModel.produto_final_id.is_(None),
                    OrcamentoPresetCncModel.produto_final_id == produto_final_id,
                )
            )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    OrcamentoPresetCncModel.codigo.ilike(pattern),
                    OrcamentoPresetCncModel.nome.ilike(pattern),
                    OrcamentoPresetCncModel.descricao.ilike(pattern),
                    OrcamentoPresetCncModel.material_referencia.ilike(pattern),
                    OrcamentoPresetCncModel.familia_peca.ilike(pattern),
                )
            )

        rows = list(
            self.db.scalars(
                stmt.order_by(
                    OrcamentoPresetCncModel.updated_at.desc(),
                    OrcamentoPresetCncModel.id.desc(),
                )
            ).all()
        )

        def _score(preset: OrcamentoPresetCncModel) -> int:
            score = 0
            if preset.cliente_id is None and preset.produto_final_id is None:
                score += 1
            if cliente_id is not None:
                if preset.cliente_id == cliente_id:
                    score += 2
                elif preset.cliente_id is not None:
                    score -= 3
            if produto_final_id is not None:
                if preset.produto_final_id == produto_final_id:
                    score += 2
                elif preset.produto_final_id is not None:
                    score -= 3
            return score

        rows.sort(
            key=lambda preset: (_score(preset), preset.updated_at, preset.id),
            reverse=True,
        )
        total = len(rows)
        start = (page - 1) * page_size
        end = start + page_size
        paged = rows[start:end]
        return [self._preset_to_payload(row) for row in paged], total

    def create_preset_cnc(self, payload: dict[str, Any]) -> dict[str, Any]:
        codigo = (payload.get("codigo") or self._generate_preset_codigo()).strip().upper()
        self._ensure_preset_codigo_unique(codigo)

        cliente_id = payload.get("cliente_id")
        if cliente_id is not None:
            self._ensure_cliente_exists(int(cliente_id))
        produto_final_id = payload.get("produto_final_id")
        if produto_final_id is not None:
            self._ensure_produto_exists(int(produto_final_id))
        centro_trabalho_id = payload.get("centro_trabalho_id")
        if centro_trabalho_id is not None:
            self._ensure_centro_exists(int(centro_trabalho_id))

        preset = OrcamentoPresetCncModel(
            versao_atual=1,
            codigo=codigo,
            nome=str(payload["nome"]).strip(),
            descricao=payload.get("descricao"),
            ativo=bool(payload.get("ativo", True)),
            cliente_id=cliente_id,
            produto_final_id=produto_final_id,
            centro_trabalho_id=centro_trabalho_id,
            fabricante_referencia=payload.get("fabricante_referencia"),
            linha_maquina_referencia=payload.get("linha_maquina_referencia"),
            perfil_maquina=payload.get("perfil_maquina"),
            familia_peca=payload.get("familia_peca"),
            tipo_peca=payload.get("tipo_peca"),
            material_referencia=payload.get("material_referencia"),
            operacao_principal=payload.get("operacao_principal"),
            diametro_referencia_mm=payload.get("diametro_referencia_mm"),
            comprimento_referencia_mm=payload.get("comprimento_referencia_mm"),
            fator_ciclo=self._to_decimal(payload.get("fator_ciclo", "1"), "fator_ciclo"),
            fator_setup=self._to_decimal(payload.get("fator_setup", "1"), "fator_setup"),
            margem_lucro_pct=self._to_decimal(
                payload.get("margem_lucro_pct", "25"),
                "margem_lucro_pct",
            ),
            custo_indireto_pct=self._to_decimal(
                payload.get("custo_indireto_pct", "6"),
                "custo_indireto_pct",
            ),
            operacoes_template_json=self._json_safe(payload.get("operacoes_template", [])),
            heuristicas_json=self._json_safe(payload.get("heuristicas", {})),
        )
        self._validate_positive("fator_ciclo", Decimal(preset.fator_ciclo))
        self._validate_positive("fator_setup", Decimal(preset.fator_setup))
        self._validate_non_negative("margem_lucro_pct", Decimal(preset.margem_lucro_pct))
        self._validate_non_negative("custo_indireto_pct", Decimal(preset.custo_indireto_pct))
        self.db.add(preset)
        self.db.flush()
        self._registrar_historico_preset(
            preset=preset,
            acao="CRIACAO",
            motivo=payload.get("motivo_versao") or "Criacao inicial de preset CNC.",
        )
        self._commit_or_409("Falha ao criar preset CNC.")
        self.db.refresh(preset)
        return self._preset_to_payload(preset)

    def update_preset_cnc(self, *, preset_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        preset = self._get_preset_or_404(preset_id)

        if "codigo" in payload and payload.get("codigo") is not None:
            codigo = str(payload["codigo"]).strip().upper()
            if codigo != preset.codigo:
                self._ensure_preset_codigo_unique(codigo)
                preset.codigo = codigo

        if "cliente_id" in payload and payload.get("cliente_id") is not None:
            self._ensure_cliente_exists(int(payload["cliente_id"]))
        if "produto_final_id" in payload and payload.get("produto_final_id") is not None:
            self._ensure_produto_exists(int(payload["produto_final_id"]))
        if "centro_trabalho_id" in payload and payload.get("centro_trabalho_id") is not None:
            self._ensure_centro_exists(int(payload["centro_trabalho_id"]))

        for field in (
            "nome",
            "descricao",
            "ativo",
            "cliente_id",
            "produto_final_id",
            "centro_trabalho_id",
            "fabricante_referencia",
            "linha_maquina_referencia",
            "perfil_maquina",
            "familia_peca",
            "tipo_peca",
            "material_referencia",
            "operacao_principal",
            "diametro_referencia_mm",
            "comprimento_referencia_mm",
        ):
            if field in payload:
                setattr(preset, field, payload.get(field))

        if "fator_ciclo" in payload:
            preset.fator_ciclo = self._to_decimal(payload["fator_ciclo"], "fator_ciclo")
            self._validate_positive("fator_ciclo", Decimal(preset.fator_ciclo))
        if "fator_setup" in payload:
            preset.fator_setup = self._to_decimal(payload["fator_setup"], "fator_setup")
            self._validate_positive("fator_setup", Decimal(preset.fator_setup))
        if "margem_lucro_pct" in payload:
            preset.margem_lucro_pct = self._to_decimal(
                payload["margem_lucro_pct"],
                "margem_lucro_pct",
            )
            self._validate_non_negative("margem_lucro_pct", Decimal(preset.margem_lucro_pct))
        if "custo_indireto_pct" in payload:
            preset.custo_indireto_pct = self._to_decimal(
                payload["custo_indireto_pct"],
                "custo_indireto_pct",
            )
            self._validate_non_negative("custo_indireto_pct", Decimal(preset.custo_indireto_pct))
        if "operacoes_template" in payload:
            preset.operacoes_template_json = self._json_safe(payload.get("operacoes_template", []))
        if "heuristicas" in payload:
            preset.heuristicas_json = self._json_safe(payload.get("heuristicas", {}))

        preset.versao_atual = int(preset.versao_atual or 1) + 1
        preset.updated_at = datetime.now(UTC)
        self._registrar_historico_preset(
            preset=preset,
            acao="ATUALIZACAO",
            motivo=payload.get("motivo_versao") or "Atualizacao manual de preset CNC.",
        )
        self._commit_or_409("Falha ao atualizar preset CNC.")
        self.db.refresh(preset)
        return self._preset_to_payload(preset)

    def recalibrar_preset_cnc(self, *, preset_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        preset = self._get_preset_or_404(preset_id)
        janela_dias = int(payload.get("janela_dias", 90))
        if janela_dias < 1 or janela_dias > 3650:
            raise HTTPException(
                status_code=HTTP_422,
                detail="janela_dias deve estar entre 1 e 3650.",
            )
        alpha = self._to_decimal(payload.get("suavizacao_alpha", "0.65"), "suavizacao_alpha")
        if alpha < 0 or alpha > 1:
            raise HTTPException(
                status_code=HTTP_422,
                detail="suavizacao_alpha deve estar entre 0 e 1.",
            )

        centro_id = payload.get("centro_trabalho_id") or preset.centro_trabalho_id
        produto_final_id = payload.get("produto_final_id") or preset.produto_final_id
        if centro_id is not None:
            self._ensure_centro_exists(int(centro_id))
        if produto_final_id is not None:
            self._ensure_produto_exists(int(produto_final_id))

        data_inicio = datetime.now(UTC).date() - timedelta(days=janela_dias)
        stmt = (
            select(OrdemOperacaoModel, OrdemProducaoModel)
            .join(OrdemProducaoModel, OrdemProducaoModel.id == OrdemOperacaoModel.ordem_id)
            .where(OrdemProducaoModel.status == "FINALIZADA")
            .where(OrdemProducaoModel.data_emissao >= data_inicio)
        )
        if centro_id is not None:
            stmt = stmt.where(OrdemOperacaoModel.centro_trabalho_id == int(centro_id))
        if produto_final_id is not None:
            stmt = stmt.where(OrdemProducaoModel.produto_final_id == int(produto_final_id))

        rows = self.db.execute(stmt).all()
        total_ratios: list[Decimal] = []
        cycle_ratios: list[Decimal] = []
        setup_ratios: list[Decimal] = []
        tempo_planejado_total = Decimal("0")
        tempo_real_total = Decimal("0")

        for operacao, ordem in rows:
            (
                real_total_min,
                first_segment_min,
                quantidade_produzida,
            ) = self._extract_mes_operation_metrics(operacao.id)
            planned_setup = Decimal(operacao.setup_planejado_min)
            planned_cycle = Decimal(operacao.ciclo_planejado_min)
            planned_total = planned_setup + (planned_cycle * Decimal(ordem.quantidade_planejada))
            if planned_total <= 0 or real_total_min <= 0:
                continue

            tempo_planejado_total += planned_total
            tempo_real_total += real_total_min

            total_ratio = self._clamp_decimal(real_total_min / planned_total, "0.30", "3.00")
            total_ratios.append(total_ratio)

            if planned_cycle > 0 and quantidade_produzida > 0:
                cycle_real_unit = (real_total_min - planned_setup) / quantidade_produzida
                cycle_ratio = self._clamp_decimal(cycle_real_unit / planned_cycle, "0.30", "3.00")
                cycle_ratios.append(cycle_ratio)
            if planned_setup > 0 and first_segment_min is not None and first_segment_min > 0:
                setup_ratio = self._clamp_decimal(first_segment_min / planned_setup, "0.30", "3.00")
                setup_ratios.append(setup_ratio)

        if not total_ratios:
            raise HTTPException(
                status_code=HTTP_422,
                detail="Nao ha amostras MES suficientes para recalibrar este preset.",
            )

        fator_cycle_sugerido = self._avg_decimal(cycle_ratios) or self._avg_decimal(total_ratios)
        fator_setup_sugerido = self._avg_decimal(setup_ratios) or self._avg_decimal(total_ratios)
        fator_cycle_anterior = Decimal(preset.fator_ciclo)
        fator_setup_anterior = Decimal(preset.fator_setup)
        fator_cycle_novo = self._blend_factor(
            current=fator_cycle_anterior,
            suggested=fator_cycle_sugerido or fator_cycle_anterior,
            alpha=alpha,
        )
        fator_setup_novo = self._blend_factor(
            current=fator_setup_anterior,
            suggested=fator_setup_sugerido or fator_setup_anterior,
            alpha=alpha,
        )

        preset.fator_ciclo = fator_cycle_novo
        preset.fator_setup = fator_setup_novo
        preset.amostras_mes = len(total_ratios)
        preset.tempo_planejado_min_total = tempo_planejado_total.quantize(Decimal("0.01"))
        preset.tempo_real_min_total = tempo_real_total.quantize(Decimal("0.01"))
        preset.ultima_calibracao_at = datetime.now(UTC)
        preset.versao_atual = int(preset.versao_atual or 1) + 1
        preset.updated_at = datetime.now(UTC)
        self._registrar_historico_preset(
            preset=preset,
            acao="RECALIBRACAO",
            motivo=payload.get("motivo_versao")
            or f"Recalibrado por MES com janela de {janela_dias} dias.",
        )

        self._commit_or_409("Falha ao recalibrar preset CNC com MES.")
        self.db.refresh(preset)

        ratio_medio = self._avg_decimal(total_ratios) or Decimal("1")
        desvio_medio_pct = (ratio_medio - Decimal("1")) * Decimal("100")
        return {
            "preset_id": preset.id,
            "preset_nome": preset.nome,
            "janela_dias": janela_dias,
            "amostras_utilizadas": len(total_ratios),
            "fator_ciclo_anterior": fator_cycle_anterior,
            "fator_ciclo_novo": Decimal(preset.fator_ciclo),
            "fator_setup_anterior": fator_setup_anterior,
            "fator_setup_novo": Decimal(preset.fator_setup),
            "tempo_planejado_min_total": Decimal(preset.tempo_planejado_min_total),
            "tempo_real_min_total": Decimal(preset.tempo_real_min_total),
            "desvio_medio_pct": desvio_medio_pct.quantize(Decimal("0.01")),
            "ultima_calibracao_at": preset.ultima_calibracao_at,
        }

    def list_preset_historico(
        self,
        *,
        preset_id: int,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        self._get_preset_or_404(preset_id)
        stmt = select(OrcamentoPresetCncHistoricoModel).where(
            OrcamentoPresetCncHistoricoModel.preset_id == preset_id
        )
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = list(
            self.db.scalars(
                stmt.order_by(
                    OrcamentoPresetCncHistoricoModel.versao.desc(),
                    OrcamentoPresetCncHistoricoModel.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return [
            {
                "id": row.id,
                "preset_id": row.preset_id,
                "versao": row.versao,
                "acao": row.acao,
                "motivo": row.motivo,
                "snapshot": row.snapshot_json or {},
                "metricas": row.metricas_json or {},
                "created_at": row.created_at,
            }
            for row in rows
        ], int(total)

    def registrar_uso_preset_cnc(
        self,
        *,
        preset_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        preset = self._aplicar_registro_uso_preset(
            preset_id=preset_id,
            tipo_evento=payload.get("tipo_evento", "APLICACAO_MANUAL"),
            erro_previsao_pct=payload.get("erro_previsao_pct"),
            observacao=payload.get("observacao"),
        )
        self._commit_or_409("Falha ao registrar uso do preset CNC.")
        self.db.refresh(preset)
        return {
            "preset_id": preset.id,
            "versao_atual": int(preset.versao_atual),
            "total_aplicacoes": int(preset.total_aplicacoes),
            "total_orcamentos": int(preset.total_orcamentos),
            "erro_absoluto_acumulado_pct": Decimal(preset.erro_absoluto_acumulado_pct),
            "ultima_aplicacao_at": preset.ultima_aplicacao_at,
        }

    def list_presets_cnc_ranking(
        self,
        *,
        limit: int,
        cliente_id: int | None = None,
        produto_final_id: int | None = None,
        centro_trabalho_id: int | None = None,
        material_referencia: str | None = None,
        familia_peca: str | None = None,
        tipo_peca: str | None = None,
    ) -> list[dict[str, Any]]:
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=HTTP_422,
                detail="limit deve estar entre 1 e 100.",
            )
        if cliente_id is not None:
            self._ensure_cliente_exists(cliente_id)
        if produto_final_id is not None:
            self._ensure_produto_exists(produto_final_id)
        if centro_trabalho_id is not None:
            self._ensure_centro_exists(centro_trabalho_id)

        stmt = select(OrcamentoPresetCncModel).where(OrcamentoPresetCncModel.ativo.is_(True))
        if cliente_id is not None:
            stmt = stmt.where(
                or_(
                    OrcamentoPresetCncModel.cliente_id.is_(None),
                    OrcamentoPresetCncModel.cliente_id == cliente_id,
                )
            )
        if produto_final_id is not None:
            stmt = stmt.where(
                or_(
                    OrcamentoPresetCncModel.produto_final_id.is_(None),
                    OrcamentoPresetCncModel.produto_final_id == produto_final_id,
                )
            )

        presets = list(self.db.scalars(stmt).all())
        ranking: list[dict[str, Any]] = []
        for preset in presets:
            score = self._calcular_scores_preset(
                preset=preset,
                cliente_id=cliente_id,
                produto_final_id=produto_final_id,
                centro_trabalho_id=centro_trabalho_id,
                material_referencia=material_referencia,
                familia_peca=familia_peca,
                tipo_peca=tipo_peca,
            )
            ranking.append(
                {
                    "preset": self._preset_to_payload(preset),
                    "score_uso": score["score_uso"],
                    "score_assertividade": score["score_assertividade"],
                    "score_contexto": score["score_contexto"],
                    "score_final": score["score_final"],
                    "motivos": score["motivos"],
                }
            )

        ranking.sort(
            key=lambda row: (row["score_final"], row["preset"]["updated_at"], row["preset"]["id"]),
            reverse=True,
        )
        return ranking[:limit]

    def suggest_preset_cnc(
        self,
        *,
        cliente_id: int | None = None,
        produto_final_id: int | None = None,
        centro_trabalho_id: int | None = None,
        material_referencia: str | None = None,
        familia_peca: str | None = None,
        tipo_peca: str | None = None,
    ) -> dict[str, Any]:
        ranked = self.list_presets_cnc_ranking(
            limit=1,
            cliente_id=cliente_id,
            produto_final_id=produto_final_id,
            centro_trabalho_id=centro_trabalho_id,
            material_referencia=material_referencia,
            familia_peca=familia_peca,
            tipo_peca=tipo_peca,
        )
        if not ranked:
            return {
                "preset": None,
                "score_final": None,
                "motivos": ["Nenhum preset ativo encontrado para o contexto informado."],
            }
        top = ranked[0]
        return {
            "preset": top["preset"],
            "score_final": top["score_final"],
            "motivos": top["motivos"],
        }

    def _create_versao(
        self,
        *,
        orcamento_id: int,
        versao: int,
        sim: dict[str, Any],
        moeda: str,
        payload: dict[str, Any],
    ) -> OrcamentoVersaoModel:
        versao_model = OrcamentoVersaoModel(
            orcamento_id=orcamento_id,
            versao=versao,
            bom_id=sim["bom_id"],
            quantidade=sim["quantidade"],
            margem_lucro_pct=sim["margem_lucro_pct"],
            custo_material_total=sim["custo_material_total"],
            custo_maquina_total=sim["custo_maquina_total"],
            custo_indireto_total=sim["custo_indireto_total"],
            preco_venda=sim["preco_venda"],
            moeda=moeda,
            detalhes_json=self._json_safe(
                {
                    "materiais": sim["materiais"],
                    "operacoes_input": payload.get("operacoes", []),
                    "parametros": {
                        "custo_indireto_fixo": payload.get("custo_indireto_fixo", Decimal("0")),
                        "custo_indireto_pct": payload.get("custo_indireto_pct", Decimal("0")),
                    },
                }
            ),
        )
        self.db.add(versao_model)
        self.db.flush()

        for op in sim["operacoes"]:
            self.db.add(
                OrcamentoVersaoOperacaoModel(
                    orcamento_versao_id=versao_model.id,
                    sequencia=op["sequencia"],
                    centro_trabalho_id=op["centro_trabalho_id"],
                    setup_min=op["setup_min"],
                    ciclo_min=op["ciclo_min"],
                    tempo_total_horas=op["tempo_total_horas"],
                    taxa_horaria=op["taxa_horaria"],
                    custo_operacao=op["custo_operacao"],
                    descricao=op.get("descricao"),
                )
            )
        return versao_model

    def _extract_pdf_text(self, file_bytes: bytes) -> str:
        if PdfReader is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Leitura de PDF indisponivel no servidor.",
            )
        try:
            reader = PdfReader(BytesIO(file_bytes))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=HTTP_422,
                detail="PDF invalido ou corrompido.",
            ) from exc
        texts: list[str] = []
        for page in reader.pages:
            page_text = (page.extract_text() or "").strip()
            if page_text:
                texts.append(page_text)
        return "\n".join(texts).strip()

    def _infer_pdf_desenho(
        self,
        text: str,
        *,
        quantidade_override: int | None,
    ) -> dict[str, Any]:
        normalized = self._normalize_for_search(text)
        quantidade_match = RE_QUANTIDADE.search(normalized)
        quantidade_inferida = int(quantidade_match.group(1)) if quantidade_match else None
        quantidade_considerada = quantidade_override or quantidade_inferida or 1

        diametros_raw = RE_DIAMETRO.findall(normalized) + RE_H7.findall(normalized)
        diametros_mm = sorted(
            {
                self._to_decimal(number.replace(",", "."), "diametro_mm")
                for number in diametros_raw
                if number.strip()
            }
        )

        comprimento_mm: Decimal | None = None
        dims_raw = RE_DIM_X.findall(normalized)
        if dims_raw:
            dim_candidates: list[Decimal] = []
            for first, second in dims_raw:
                dim_candidates.extend(
                    [
                        self._to_decimal(first.replace(",", "."), "dimensao_pdf"),
                        self._to_decimal(second.replace(",", "."), "dimensao_pdf"),
                    ]
                )
            if dim_candidates:
                comprimento_mm = max(dim_candidates)

        material_inferido = None
        for keyword in MATERIAL_PRECO_KG:
            if keyword in normalized:
                material_inferido = keyword
                break

        confidence_score = 0
        if material_inferido:
            confidence_score += 1
        if quantidade_inferida is not None:
            confidence_score += 1
        if diametros_mm:
            confidence_score += 1
        if comprimento_mm is not None:
            confidence_score += 1

        if confidence_score >= 3:
            confianca = "ALTA"
        elif confidence_score == 2:
            confianca = "MEDIA"
        else:
            confianca = "BAIXA"

        texto_resumo = " ".join(text.split())[:600] if text else "PDF sem texto extraivel."
        premissas: list[str] = []
        if not material_inferido:
            premissas.append("Material nao identificado no PDF. Padrao usado: ACO CARBONO.")
        if not diametros_mm:
            premissas.append("Diametros nao identificados. Diametro de referencia padrao: 50 mm.")
        if comprimento_mm is None:
            premissas.append("Comprimento nao identificado. Comprimento padrao: 100 mm.")
        if quantidade_inferida is None and quantidade_override is None:
            premissas.append("Quantidade nao identificada. Quantidade considerada: 1.")
        if not text:
            premissas.append("PDF pode ser imagem escaneada sem OCR; leitura textual limitada.")

        return {
            "material_inferido": material_inferido,
            "quantidade_inferida": quantidade_inferida,
            "quantidade_considerada": quantidade_considerada,
            "diametros_mm": diametros_mm,
            "comprimento_mm": comprimento_mm,
            "confianca": confianca,
            "texto_resumo": texto_resumo,
            "premissas": premissas,
        }

    def _estimate_material_unit_cost(self, inferencia: dict[str, Any]) -> Decimal:
        material = inferencia.get("material_inferido") or "ACO CARBONO"
        preco_kg = MATERIAL_PRECO_KG.get(material, Decimal("9.50"))
        densidade = MATERIAL_DENSIDADE_G_CM3.get(material, Decimal("7.85"))

        diametros: list[Decimal] = inferencia.get("diametros_mm") or []
        diametro_ref = max(diametros) if diametros else Decimal("50")
        comprimento_mm = inferencia.get("comprimento_mm") or Decimal("100")

        pi = Decimal("3.14159265")
        raio_mm = diametro_ref / Decimal("2")
        volume_mm3 = pi * raio_mm * raio_mm * comprimento_mm
        volume_cm3 = volume_mm3 / Decimal("1000")
        massa_kg = (volume_cm3 * densidade) / Decimal("1000")
        if massa_kg <= 0:
            massa_kg = Decimal("1")
        custo = massa_kg * preco_kg
        return custo.quantize(Decimal("0.0001"))

    def _estimate_machine_hours_unit(
        self,
        *,
        inferencia: dict[str, Any],
        setup_padrao_min: Decimal,
    ) -> Decimal:
        quantidade = Decimal(inferencia["quantidade_considerada"])
        diametros_count = max(1, len(inferencia.get("diametros_mm") or []))
        comprimento_mm = inferencia.get("comprimento_mm") or Decimal("100")

        setup_h_por_unidade = (setup_padrao_min / Decimal("60")) / quantidade
        complexidade_h = Decimal(diametros_count) * Decimal("0.03")
        percurso_h = (Decimal(comprimento_mm) / Decimal("1000")) * Decimal("0.12")
        base_h = Decimal("0.05")
        horas = base_h + setup_h_por_unidade + complexidade_h + percurso_h
        if horas < Decimal("0.08"):
            horas = Decimal("0.08")
        return horas.quantize(Decimal("0.0001"))

    def _normalize_for_search(self, text: str) -> str:
        if not text:
            return ""
        text_nfkd = unicodedata.normalize("NFKD", text)
        ascii_text = text_nfkd.encode("ASCII", "ignore").decode("ASCII")
        return ascii_text.upper()

    def _upload_root_path(self) -> Path:
        settings = get_settings()
        return Path(settings.uploads_dir).expanduser().resolve()

    def _anexo_to_payload(self, anexo: OrcamentoAnexoModel) -> dict[str, Any]:
        return {
            "id": anexo.id,
            "orcamento_id": anexo.orcamento_id,
            "nome_arquivo_original": anexo.nome_arquivo_original,
            "content_type": anexo.content_type,
            "tamanho_bytes": anexo.tamanho_bytes,
            "observacao": anexo.observacao,
            "uploaded_at": anexo.uploaded_at,
            "download_path": f"/api/v1/orcamentos/anexos/{anexo.id}/download",
        }

    def _preset_to_payload(self, preset: OrcamentoPresetCncModel) -> dict[str, Any]:
        operacoes_template = []
        for idx, op in enumerate(preset.operacoes_template_json or [], start=1):
            operacoes_template.append(
                {
                    "sequencia": int(op.get("sequencia", idx)),
                    "centro_trabalho_id": op.get("centro_trabalho_id"),
                    "setup_min": self._decimal_or_default(op.get("setup_min"), "0"),
                    "ciclo_min": self._decimal_or_default(op.get("ciclo_min"), "0"),
                    "descricao": op.get("descricao"),
                }
            )
        return {
            "id": preset.id,
            "versao_atual": int(preset.versao_atual or 1),
            "codigo": preset.codigo,
            "nome": preset.nome,
            "descricao": preset.descricao,
            "ativo": bool(preset.ativo),
            "cliente_id": preset.cliente_id,
            "produto_final_id": preset.produto_final_id,
            "centro_trabalho_id": preset.centro_trabalho_id,
            "fabricante_referencia": preset.fabricante_referencia,
            "linha_maquina_referencia": preset.linha_maquina_referencia,
            "perfil_maquina": preset.perfil_maquina,
            "familia_peca": preset.familia_peca,
            "tipo_peca": preset.tipo_peca,
            "material_referencia": preset.material_referencia,
            "operacao_principal": preset.operacao_principal,
            "diametro_referencia_mm": preset.diametro_referencia_mm,
            "comprimento_referencia_mm": preset.comprimento_referencia_mm,
            "fator_ciclo": preset.fator_ciclo,
            "fator_setup": preset.fator_setup,
            "margem_lucro_pct": preset.margem_lucro_pct,
            "custo_indireto_pct": preset.custo_indireto_pct,
            "operacoes_template": operacoes_template,
            "heuristicas": preset.heuristicas_json or {},
            "amostras_mes": int(preset.amostras_mes or 0),
            "total_aplicacoes": int(preset.total_aplicacoes or 0),
            "total_orcamentos": int(preset.total_orcamentos or 0),
            "erro_absoluto_acumulado_pct": Decimal(preset.erro_absoluto_acumulado_pct or 0),
            "tempo_planejado_min_total": preset.tempo_planejado_min_total,
            "tempo_real_min_total": preset.tempo_real_min_total,
            "ultima_calibracao_at": preset.ultima_calibracao_at,
            "ultima_aplicacao_at": preset.ultima_aplicacao_at,
            "created_at": preset.created_at,
            "updated_at": preset.updated_at,
        }

    def _registrar_historico_preset(
        self,
        *,
        preset: OrcamentoPresetCncModel,
        acao: str,
        motivo: str | None,
    ) -> None:
        motivo_limpo = str(motivo).strip() if motivo is not None else None
        if motivo_limpo == "":
            motivo_limpo = None
        self.db.add(
            OrcamentoPresetCncHistoricoModel(
                preset_id=preset.id,
                versao=int(preset.versao_atual or 1),
                acao=acao,
                motivo=motivo_limpo,
                snapshot_json=self._json_safe(self._snapshot_preset(preset)),
                metricas_json=self._json_safe(self._metricas_preset(preset)),
            )
        )

    def _snapshot_preset(self, preset: OrcamentoPresetCncModel) -> dict[str, Any]:
        return {
            "codigo": preset.codigo,
            "nome": preset.nome,
            "descricao": preset.descricao,
            "ativo": bool(preset.ativo),
            "cliente_id": preset.cliente_id,
            "produto_final_id": preset.produto_final_id,
            "centro_trabalho_id": preset.centro_trabalho_id,
            "fabricante_referencia": preset.fabricante_referencia,
            "linha_maquina_referencia": preset.linha_maquina_referencia,
            "perfil_maquina": preset.perfil_maquina,
            "familia_peca": preset.familia_peca,
            "tipo_peca": preset.tipo_peca,
            "material_referencia": preset.material_referencia,
            "operacao_principal": preset.operacao_principal,
            "diametro_referencia_mm": preset.diametro_referencia_mm,
            "comprimento_referencia_mm": preset.comprimento_referencia_mm,
            "fator_ciclo": preset.fator_ciclo,
            "fator_setup": preset.fator_setup,
            "margem_lucro_pct": preset.margem_lucro_pct,
            "custo_indireto_pct": preset.custo_indireto_pct,
            "operacoes_template": preset.operacoes_template_json or [],
            "heuristicas": preset.heuristicas_json or {},
        }

    def _metricas_preset(self, preset: OrcamentoPresetCncModel) -> dict[str, Any]:
        return {
            "versao_atual": int(preset.versao_atual or 1),
            "amostras_mes": int(preset.amostras_mes or 0),
            "total_aplicacoes": int(preset.total_aplicacoes or 0),
            "total_orcamentos": int(preset.total_orcamentos or 0),
            "erro_absoluto_acumulado_pct": Decimal(preset.erro_absoluto_acumulado_pct or 0),
            "tempo_planejado_min_total": Decimal(preset.tempo_planejado_min_total or 0),
            "tempo_real_min_total": Decimal(preset.tempo_real_min_total or 0),
            "ultima_calibracao_at": preset.ultima_calibracao_at,
            "ultima_aplicacao_at": preset.ultima_aplicacao_at,
        }

    def _aplicar_registro_uso_preset(
        self,
        *,
        preset_id: int,
        tipo_evento: Any,
        erro_previsao_pct: Any,
        observacao: str | None,
    ) -> OrcamentoPresetCncModel:
        preset = self._get_preset_or_404(preset_id)
        tipo_evento_norm = str(tipo_evento or "APLICACAO_MANUAL").strip().upper()
        erro_decimal: Decimal | None = None
        if erro_previsao_pct is not None:
            erro_decimal = self._to_decimal(erro_previsao_pct, "erro_previsao_pct")
            self._validate_non_negative("erro_previsao_pct", erro_decimal)

        preset.total_aplicacoes = int(preset.total_aplicacoes or 0) + 1
        if tipo_evento_norm in USO_EVENTOS_COM_ORCAMENTO:
            preset.total_orcamentos = int(preset.total_orcamentos or 0) + 1
        if erro_decimal is not None:
            acumulado = Decimal(preset.erro_absoluto_acumulado_pct or 0) + abs(erro_decimal)
            preset.erro_absoluto_acumulado_pct = acumulado.quantize(Decimal("0.0001"))

        if observacao:
            heuristicas = dict(preset.heuristicas_json or {})
            historico_uso = list(heuristicas.get("historico_uso", []))
            historico_uso.append(
                {
                    "tipo_evento": tipo_evento_norm,
                    "observacao": str(observacao)[:300],
                    "at": datetime.now(UTC).isoformat(),
                }
            )
            heuristicas["historico_uso"] = historico_uso[-5:]
            preset.heuristicas_json = self._json_safe(heuristicas)

        preset.ultima_aplicacao_at = datetime.now(UTC)
        preset.updated_at = datetime.now(UTC)
        return preset

    def _calcular_scores_preset(
        self,
        *,
        preset: OrcamentoPresetCncModel,
        cliente_id: int | None,
        produto_final_id: int | None,
        centro_trabalho_id: int | None,
        material_referencia: str | None,
        familia_peca: str | None,
        tipo_peca: str | None,
    ) -> dict[str, Any]:
        motivos: list[str] = []
        total_aplicacoes = Decimal(int(preset.total_aplicacoes or 0))
        total_orcamentos = Decimal(int(preset.total_orcamentos or 0))
        score_uso = min(
            Decimal("30"),
            (total_aplicacoes * Decimal("1.5")) + (total_orcamentos * Decimal("2.5")),
        )
        if total_aplicacoes > 0:
            motivos.append(
                "Uso acumulado: "
                f"{int(total_aplicacoes)} aplicacoes, "
                f"{int(total_orcamentos)} orcamentos."
            )
        else:
            motivos.append("Preset ainda sem uso real registrado.")

        score_assertividade = Decimal("18")
        tempo_planejado = Decimal(preset.tempo_planejado_min_total or 0)
        tempo_real = Decimal(preset.tempo_real_min_total or 0)
        amostras_mes = int(preset.amostras_mes or 0)
        if amostras_mes > 0 and tempo_planejado > 0 and tempo_real > 0:
            desvio_pct = abs((tempo_real - tempo_planejado) / tempo_planejado) * Decimal("100")
            score_assertividade = max(Decimal("0"), Decimal("40") - desvio_pct)
            motivos.append(
                f"Assertividade MES com {amostras_mes} amostras "
                f"(desvio medio {desvio_pct.quantize(Decimal('0.01'))}%)."
            )
        else:
            motivos.append("Sem base MES suficiente; assertividade neutra.")

        erro_abs = Decimal(preset.erro_absoluto_acumulado_pct or 0)
        if total_orcamentos > 0 and erro_abs > 0:
            erro_medio = erro_abs / total_orcamentos
            penalidade = min(Decimal("15"), erro_medio / Decimal("2"))
            score_assertividade = max(Decimal("0"), score_assertividade - penalidade)
            motivos.append(
                f"Penalidade de erro historico medio {erro_medio.quantize(Decimal('0.01'))}%."
            )

        score_contexto = Decimal("0")
        if cliente_id is not None:
            if preset.cliente_id == cliente_id:
                score_contexto += Decimal("12")
                motivos.append("Match exato por cliente.")
            elif preset.cliente_id is None:
                score_contexto += Decimal("4")
        elif preset.cliente_id is None:
            score_contexto += Decimal("2")

        if produto_final_id is not None:
            if preset.produto_final_id == produto_final_id:
                score_contexto += Decimal("12")
                motivos.append("Match exato por produto.")
            elif preset.produto_final_id is None:
                score_contexto += Decimal("4")
        elif preset.produto_final_id is None:
            score_contexto += Decimal("2")

        if centro_trabalho_id is not None:
            if preset.centro_trabalho_id == centro_trabalho_id:
                score_contexto += Decimal("4")
                motivos.append("Centro de trabalho alinhado.")
            elif preset.centro_trabalho_id is None:
                score_contexto += Decimal("1")

        if self._same_lookup_value(preset.material_referencia, material_referencia):
            score_contexto += Decimal("2")
            motivos.append("Material de referencia compatível.")
        if self._same_lookup_value(preset.familia_peca, familia_peca):
            score_contexto += Decimal("2")
            motivos.append("Familia de peca compatível.")
        if self._same_lookup_value(preset.tipo_peca, tipo_peca):
            score_contexto += Decimal("1")
            motivos.append("Tipo de peca compatível.")

        if score_contexto > Decimal("30"):
            score_contexto = Decimal("30")

        score_final = (score_uso + score_assertividade + score_contexto).quantize(Decimal("0.01"))
        return {
            "score_uso": score_uso.quantize(Decimal("0.01")),
            "score_assertividade": score_assertividade.quantize(Decimal("0.01")),
            "score_contexto": score_contexto.quantize(Decimal("0.01")),
            "score_final": score_final,
            "motivos": motivos[:6],
        }

    def _same_lookup_value(self, left: str | None, right: str | None) -> bool:
        if not left or not right:
            return False
        return self._normalize_for_search(left) == self._normalize_for_search(right)

    def _extract_mes_operation_metrics(
        self,
        ordem_operacao_id: int,
    ) -> tuple[Decimal, Decimal | None, Decimal]:
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
        total_seconds = Decimal("0")
        first_segment_min: Decimal | None = None
        active_since: datetime | None = None
        quantidade_produzida = Decimal("0")
        for evento in eventos:
            event_at = self._normalize_event_datetime(evento.data_hora_evento)
            quantidade_produzida += Decimal(evento.quantidade_produzida)
            if evento.evento in {"START", "RETOMADA"}:
                if active_since is None:
                    active_since = event_at
                continue
            if evento.evento in {"PAUSA", "STOP"} and active_since is not None:
                delta_seconds = Decimal((event_at - active_since).total_seconds())
                if delta_seconds > 0:
                    total_seconds += delta_seconds
                    if first_segment_min is None:
                        first_segment_min = (delta_seconds / Decimal("60")).quantize(
                            Decimal("0.0001")
                        )
                active_since = None

        total_minutes = (total_seconds / Decimal("60")).quantize(Decimal("0.0001"))
        return total_minutes, first_segment_min, quantidade_produzida

    def _avg_decimal(self, values: list[Decimal]) -> Decimal | None:
        if not values:
            return None
        return (sum(values, start=Decimal("0")) / Decimal(len(values))).quantize(Decimal("0.0001"))

    def _blend_factor(self, *, current: Decimal, suggested: Decimal, alpha: Decimal) -> Decimal:
        one = Decimal("1")
        blended = (current * (one - alpha)) + (suggested * alpha)
        return self._clamp_decimal(blended, "0.30", "3.00")

    def _clamp_decimal(self, value: Decimal, min_value: str, max_value: str) -> Decimal:
        low = Decimal(min_value)
        high = Decimal(max_value)
        return min(high, max(low, value)).quantize(Decimal("0.0001"))

    def _normalize_event_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _decimal_or_default(self, value: Any, default: str) -> Decimal:
        try:
            return Decimal(str(value if value is not None else default))
        except Exception:  # noqa: BLE001
            return Decimal(default)

    def _simulate_operacoes(
        self,
        *,
        operacoes_input: list[dict[str, Any]],
        quantidade: Decimal,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for idx, op in enumerate(operacoes_input, start=1):
            centro = self._ensure_centro_exists(int(op["centro_trabalho_id"]))
            setup_default = Decimal(centro.setup_padrao_min or 0)
            setup_min = self._to_decimal(op.get("setup_min", setup_default), "setup_min")
            ciclo_min = self._to_decimal(op.get("ciclo_min", Decimal("0")), "ciclo_min")

            self._validate_non_negative("setup_min", setup_min)
            self._validate_non_negative("ciclo_min", ciclo_min)

            tempo_total_min = setup_min + (ciclo_min * quantidade)
            tempo_total_horas = tempo_total_min / Decimal("60")
            taxa_horaria = Decimal(centro.taxa_horaria)
            custo_operacao = tempo_total_horas * taxa_horaria

            result.append(
                {
                    "sequencia": idx,
                    "centro_trabalho_id": centro.id,
                    "codigo_centro": centro.codigo,
                    "nome_centro": centro.nome,
                    "setup_min": setup_min,
                    "ciclo_min": ciclo_min,
                    "tempo_total_horas": tempo_total_horas,
                    "taxa_horaria": taxa_horaria,
                    "custo_operacao": custo_operacao,
                    "descricao": op.get("descricao"),
                }
            )
        return result

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
                    detail="BOM informada nao pertence ao produto_final_id.",
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
                detail="Produto sem BOM cadastrada para orcamento.",
            )
        return bom

    def _latest_versions_for(self, orcamento_ids: list[int]) -> dict[int, dict[str, Any]]:
        if not orcamento_ids:
            return {}

        versoes = list(
            self.db.scalars(
                select(OrcamentoVersaoModel)
                .where(OrcamentoVersaoModel.orcamento_id.in_(orcamento_ids))
                .order_by(
                    OrcamentoVersaoModel.orcamento_id,
                    OrcamentoVersaoModel.versao.desc(),
                )
            ).all()
        )
        latest: dict[int, dict[str, Any]] = {}
        for versao in versoes:
            if versao.orcamento_id in latest:
                continue
            latest[versao.orcamento_id] = {
                "versao": versao.versao,
                "preco_venda": versao.preco_venda,
            }
        return latest

    def _operacoes_por_versao(self, versao_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        if not versao_ids:
            return {}
        rows = self.db.execute(
            select(OrcamentoVersaoOperacaoModel, CentroTrabalhoModel)
            .join(
                CentroTrabalhoModel,
                CentroTrabalhoModel.id == OrcamentoVersaoOperacaoModel.centro_trabalho_id,
            )
            .where(OrcamentoVersaoOperacaoModel.orcamento_versao_id.in_(versao_ids))
            .order_by(
                OrcamentoVersaoOperacaoModel.orcamento_versao_id,
                OrcamentoVersaoOperacaoModel.sequencia,
            )
        ).all()

        grouped: dict[int, list[dict[str, Any]]] = {}
        for op, centro in rows:
            grouped.setdefault(op.orcamento_versao_id, []).append(
                {
                    "sequencia": op.sequencia,
                    "centro_trabalho_id": op.centro_trabalho_id,
                    "codigo_centro": centro.codigo,
                    "nome_centro": centro.nome,
                    "setup_min": op.setup_min,
                    "ciclo_min": op.ciclo_min,
                    "tempo_total_horas": op.tempo_total_horas,
                    "taxa_horaria": op.taxa_horaria,
                    "custo_operacao": op.custo_operacao,
                    "descricao": op.descricao,
                }
            )
        return grouped

    def _next_versao(self, orcamento_id: int) -> int:
        max_versao = self.db.scalar(
            select(func.max(OrcamentoVersaoModel.versao)).where(
                OrcamentoVersaoModel.orcamento_id == orcamento_id
            )
        )
        return int(max_versao or 0) + 1

    def _generate_codigo(self) -> str:
        return f"ORC-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')[:17]}"

    def _ensure_codigo_orcamento_unique(self, codigo: str) -> None:
        existing_id = self.db.scalar(
            select(OrcamentoModel.id).where(OrcamentoModel.codigo == codigo)
        )
        if existing_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Codigo de orcamento ja cadastrado.",
            )

    def _ensure_cliente_exists(self, cliente_id: int) -> ClienteModel:
        cliente = self.db.get(ClienteModel, cliente_id)
        if cliente is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente nao encontrado.",
            )
        return cliente

    def _ensure_produto_exists(self, produto_id: int) -> ProdutoFinalModel:
        produto = self.db.get(ProdutoFinalModel, produto_id)
        if produto is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Produto final nao encontrado.",
            )
        return produto

    def _ensure_centro_exists(self, centro_id: int) -> CentroTrabalhoModel:
        centro = self.db.get(CentroTrabalhoModel, centro_id)
        if centro is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Centro de trabalho nao encontrado.",
            )
        return centro

    def _get_orcamento_or_404(self, orcamento_id: int) -> OrcamentoModel:
        orcamento = self.db.get(OrcamentoModel, orcamento_id)
        if orcamento is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Orcamento nao encontrado.",
            )
        return orcamento

    def _get_preset_or_404(self, preset_id: int) -> OrcamentoPresetCncModel:
        preset = self.db.get(OrcamentoPresetCncModel, preset_id)
        if preset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preset CNC nao encontrado.",
            )
        return preset

    def _generate_preset_codigo(self) -> str:
        return f"PRCNC-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')[:17]}"

    def _ensure_preset_codigo_unique(self, codigo: str) -> None:
        existing_id = self.db.scalar(
            select(OrcamentoPresetCncModel.id).where(OrcamentoPresetCncModel.codigo == codigo)
        )
        if existing_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Codigo de preset CNC ja cadastrado.",
            )

    def _normalize_moeda(self, moeda: Any) -> str:
        moeda_str = str(moeda or "BRL").upper().strip()
        if len(moeda_str) < 3 or len(moeda_str) > 10:
            raise HTTPException(
                status_code=HTTP_422,
                detail="moeda deve possuir entre 3 e 10 caracteres.",
            )
        return moeda_str

    def _to_decimal(self, value: Any, field_name: str) -> Decimal:
        try:
            return Decimal(str(value))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=HTTP_422,
                detail=f"Valor invalido para {field_name}.",
            ) from exc

    def _validate_non_negative(self, field_name: str, value: Decimal) -> None:
        if value < 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail=f"{field_name} nao pode ser negativo.",
            )

    def _validate_positive(self, field_name: str, value: Decimal) -> None:
        if value <= 0:
            raise HTTPException(
                status_code=HTTP_422,
                detail=f"{field_name} deve ser maior que zero.",
            )

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
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
            if "uq_orcamento_versao" in str(exc.orig):
                detail = "Versao de orcamento duplicada."
            if "orcamentos_codigo_key" in str(exc.orig):
                detail = "Codigo de orcamento ja cadastrado."
            if "orcamento_presets_cnc_codigo_key" in str(exc.orig):
                detail = "Codigo de preset CNC ja cadastrado."
            if "uq_orc_preset_hist_versao" in str(exc.orig):
                detail = "Historico de versao do preset CNC em conflito."
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
