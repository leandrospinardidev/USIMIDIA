from __future__ import annotations

from pathlib import Path
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import get_settings
from modules.cadastro.infrastructure.models import (
    CentroTrabalhoModel,
    ClienteModel,
    ProdutoFinalModel,
)
from modules.engenharia_bom.application.services import BomService
from modules.engenharia_bom.infrastructure.models import BomModel
from modules.orcamentos.infrastructure.models import (
    OrcamentoAnexoModel,
    OrcamentoModel,
    OrcamentoVersaoModel,
    OrcamentoVersaoOperacaoModel,
)

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
            if "uq_orcamento_versao" in str(exc.orig):
                detail = "Versao de orcamento duplicada."
            if "orcamentos_codigo_key" in str(exc.orig):
                detail = "Codigo de orcamento ja cadastrado."
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=detail,
            ) from exc
