import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  criarOrcamento,
  downloadOrcamentoAnexo,
  getOrcamento,
  listBomsByProduto,
  listCentrosCadastro,
  listClientesCadastro,
  listOrcamentos,
  listProdutosCadastro,
  simularOrcamento,
  simularOrcamentoPorPdf,
  uploadOrcamentoAnexo,
} from "../api";
import {
  CNC_MACHINE_PRESETS,
  CNC_MANUFACTURER_PROFILES,
  CNC_MATERIAL_PRESETS,
  CNC_OPERATION_PRESETS,
  CNC_PIECE_FAMILIES,
  type CncPieceType,
  buildAutoStrategyPlan,
  calculateCycleMinFromPreset,
  calculateSetupMinFromPreset,
  suggestCentroForMachinePreset,
} from "../data/cncPresets";
import type {
  BomListItem,
  CentroTrabalhoCadastro,
  ClienteCadastro,
  OrcamentoDetail,
  OrcamentoListItem,
  OrcamentoOperacaoInput,
  OrcamentoPdfSimulacao,
  OrcamentoSimulacao,
  ProdutoFinalCadastro,
} from "../types";
import { extractErrorMessage } from "../utils/errors";
import { formatDateTime, formatNumber, statusBadge } from "../utils/ui";
import { Metric } from "./Metric";
import type { StandardPanelProps } from "./panels/types";

const ORCAMENTO_STATUS_FILTERS = ["", "RASCUNHO", "ENVIADO", "APROVADO", "REJEITADO"] as const;
const PRESET_NOTE_TAG = "[PRESET_CNC]";
const AUTO_STRATEGY_NOTE_TAG = "[AUTO_ESTRATEGIA]";

interface OperacaoDraft {
  centro_trabalho_id: number | "";
  setup_min: string;
  ciclo_min: string;
  descricao: string;
}

export function OrcamentosPanel({ role, isActive, onError, onSuccess }: StandardPanelProps) {
  const [clientes, setClientes] = useState<ClienteCadastro[]>([]);
  const [produtos, setProdutos] = useState<ProdutoFinalCadastro[]>([]);
  const [centros, setCentros] = useState<CentroTrabalhoCadastro[]>([]);
  const [boms, setBoms] = useState<BomListItem[]>([]);

  const [loadingCatalogos, setLoadingCatalogos] = useState(false);
  const [loadingBoms, setLoadingBoms] = useState(false);
  const [loadingOrcamentos, setLoadingOrcamentos] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [searchInput, setSearchInput] = useState("");
  const [searchApplied, setSearchApplied] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [orcamentos, setOrcamentos] = useState<OrcamentoListItem[]>([]);

  const [selectedOrcamentoId, setSelectedOrcamentoId] = useState<number | null>(null);
  const [selectedOrcamento, setSelectedOrcamento] = useState<OrcamentoDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [codigo, setCodigo] = useState("");
  const [referenciaProjeto, setReferenciaProjeto] = useState("");
  const [clienteId, setClienteId] = useState<number | "">("");
  const [produtoId, setProdutoId] = useState<number | "">("");
  const [bomId, setBomId] = useState<number | "">("");
  const [quantidade, setQuantidade] = useState("1");
  const [margemLucroPct, setMargemLucroPct] = useState("");
  const [custoIndiretoFixo, setCustoIndiretoFixo] = useState("0");
  const [custoIndiretoPct, setCustoIndiretoPct] = useState("0");
  const [observacao, setObservacao] = useState("");
  const [simulacao, setSimulacao] = useState<OrcamentoSimulacao | null>(null);
  const [pdfCentroId, setPdfCentroId] = useState<number | "">("");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfQuantidadeOverride, setPdfQuantidadeOverride] = useState("");
  const [pdfSimulacao, setPdfSimulacao] = useState<OrcamentoPdfSimulacao | null>(null);

  const [operacoes, setOperacoes] = useState<OperacaoDraft[]>([
    { centro_trabalho_id: "", setup_min: "0", ciclo_min: "0", descricao: "" },
  ]);

  const [fileToUpload, setFileToUpload] = useState<File | null>(null);
  const [fileObs, setFileObs] = useState("");
  const [showSavedModule, setShowSavedModule] = useState(false);
  const [manufacturerProfileId, setManufacturerProfileId] = useState(
    CNC_MANUFACTURER_PROFILES[0]?.id ?? ""
  );
  const [presetMachineId, setPresetMachineId] = useState(CNC_MACHINE_PRESETS[1]?.id ?? "");
  const [presetMaterialId, setPresetMaterialId] = useState(CNC_MATERIAL_PRESETS[0]?.id ?? "");
  const [presetOperationId, setPresetOperationId] = useState(CNC_OPERATION_PRESETS[0]?.id ?? "");
  const [pieceFamilyId, setPieceFamilyId] = useState(CNC_PIECE_FAMILIES[0]?.id ?? "");
  const [pieceType, setPieceType] = useState<CncPieceType>("EIXO");
  const [pieceDiametroMm, setPieceDiametroMm] = useState("");
  const [pieceComprimentoMm, setPieceComprimentoMm] = useState("");

  const totalPages = Math.max(1, Math.ceil(total / 10));

  const produtoSelecionado = useMemo(
    () => produtos.find((produto) => produto.id === produtoId) ?? null,
    [produtoId, produtos]
  );
  const suggestedCycleMin = useMemo(() => {
    const horas = Number(pdfSimulacao?.custos.horas_maquina_estimadas_unit);
    if (!Number.isFinite(horas) || horas <= 0) {
      return "8.00";
    }
    return (horas * 60).toFixed(2);
  }, [pdfSimulacao]);
  const operacaoPrincipal: OperacaoDraft = operacoes[0] ?? {
    centro_trabalho_id: "",
    setup_min: "0",
    ciclo_min: "0",
    descricao: "",
  };
  const presetMachine = useMemo(
    () => CNC_MACHINE_PRESETS.find((item) => item.id === presetMachineId) ?? CNC_MACHINE_PRESETS[0],
    [presetMachineId]
  );
  const presetMaterial = useMemo(
    () => CNC_MATERIAL_PRESETS.find((item) => item.id === presetMaterialId) ?? CNC_MATERIAL_PRESETS[0],
    [presetMaterialId]
  );
  const presetOperation = useMemo(
    () => CNC_OPERATION_PRESETS.find((item) => item.id === presetOperationId) ?? CNC_OPERATION_PRESETS[0],
    [presetOperationId]
  );
  const manufacturerProfile = useMemo(
    () =>
      CNC_MANUFACTURER_PROFILES.find((item) => item.id === manufacturerProfileId) ??
      CNC_MANUFACTURER_PROFILES[0],
    [manufacturerProfileId]
  );
  const pieceFamily = useMemo(
    () => CNC_PIECE_FAMILIES.find((item) => item.id === pieceFamilyId) ?? CNC_PIECE_FAMILIES[0],
    [pieceFamilyId]
  );
  const presetCycleMin = useMemo(() => {
    if (!presetMachine || !presetMaterial || !presetOperation) {
      return "8.00";
    }
    return calculateCycleMinFromPreset(
      presetMachine,
      presetMaterial,
      presetOperation,
      manufacturerProfile
    );
  }, [presetMachine, presetMaterial, presetOperation, manufacturerProfile]);
  const autoStrategyPlan = useMemo(() => {
    if (!presetMachine || !presetMaterial) {
      return null;
    }
    return buildAutoStrategyPlan({
      machinePreset: presetMachine,
      materialPreset: presetMaterial,
      pieceType: pieceFamily?.pieceType ?? pieceType,
      pieceFamily,
      manufacturerProfile,
      diametroMm: pieceDiametroMm ? Number(pieceDiametroMm) : null,
      comprimentoMm: pieceComprimentoMm ? Number(pieceComprimentoMm) : null,
    });
  }, [
    presetMachine,
    presetMaterial,
    pieceType,
    pieceFamily,
    manufacturerProfile,
    pieceDiametroMm,
    pieceComprimentoMm,
  ]);

  useEffect(() => {
    if (!isActive) {
      return;
    }
    if (role === "operador") {
      return;
    }
    void loadCatalogos();
  }, [isActive, role]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isActive) {
      return;
    }
    if (role === "operador") {
      setOrcamentos([]);
      setTotal(0);
      return;
    }
    if (!showSavedModule) {
      return;
    }
    void loadOrcamentos();
  }, [isActive, role, page, searchApplied, statusFilter, showSavedModule]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!produtoId || !isActive) {
      setBoms([]);
      setBomId("");
      return;
    }
    if (role === "operador") {
      return;
    }
    void loadBoms(produtoId);
  }, [produtoId, isActive, role]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!pieceFamily) {
      return;
    }
    setPieceType(pieceFamily.pieceType);
    if (!pieceDiametroMm) {
      setPieceDiametroMm(String(pieceFamily.default_diametro_mm));
    }
    if (!pieceComprimentoMm) {
      setPieceComprimentoMm(String(pieceFamily.default_comprimento_mm));
    }
  }, [pieceFamily]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadCatalogos(): Promise<void> {
    setLoadingCatalogos(true);
    onError(null);
    try {
      const [clientesResp, produtosResp, centrosResp] = await Promise.all([
        listClientesCadastro(role),
        listProdutosCadastro(role),
        listCentrosCadastro(role),
      ]);
      setClientes(clientesResp.items);
      setProdutos(produtosResp.items);
      setCentros(centrosResp.items);
    } catch (error) {
      onError(extractErrorMessage(error));
    } finally {
      setLoadingCatalogos(false);
    }
  }

  async function loadBoms(produtoFinalId: number): Promise<void> {
    setLoadingBoms(true);
    onError(null);
    try {
      const response = await listBomsByProduto(role, produtoFinalId);
      setBoms(response.items);
    } catch (error) {
      onError(extractErrorMessage(error));
    } finally {
      setLoadingBoms(false);
    }
  }

  async function loadOrcamentos(): Promise<void> {
    setLoadingOrcamentos(true);
    onError(null);
    try {
      const response = await listOrcamentos(role, {
        page,
        pageSize: 10,
        search: searchApplied || undefined,
        status: statusFilter || undefined,
      });
      setOrcamentos(response.items);
      setTotal(response.meta.total);
      if (selectedOrcamentoId && !response.items.some((item) => item.id === selectedOrcamentoId)) {
        setSelectedOrcamentoId(null);
        setSelectedOrcamento(null);
      }
    } catch (error) {
      onError(extractErrorMessage(error));
    } finally {
      setLoadingOrcamentos(false);
    }
  }

  function validateMainForm(): string | null {
    if (!produtoId) {
      return "Selecione o produto final.";
    }
    if (!quantidade || Number(quantidade) <= 0) {
      return "Quantidade deve ser maior que zero.";
    }
    const hasValidOperacao = operacoes.some((op) => op.centro_trabalho_id !== "") || Boolean(pdfCentroId);
    if (!hasValidOperacao) {
      return "Informe ao menos um centro de usinagem para a operacao principal.";
    }
    return null;
  }

  function buildOperacoesPayload(): OrcamentoOperacaoInput[] {
    const mapped = operacoes
      .filter((op) => op.centro_trabalho_id !== "")
      .map((op) => ({
        centro_trabalho_id: Number(op.centro_trabalho_id),
        setup_min: op.setup_min || "0",
        ciclo_min: op.ciclo_min || "0",
        descricao: op.descricao.trim() || undefined,
      }));
    if (mapped.length > 0) {
      return mapped;
    }
    if (pdfCentroId) {
      return [
        {
          centro_trabalho_id: Number(pdfCentroId),
          setup_min: "0",
          ciclo_min: suggestedCycleMin,
          descricao: "Usinagem CNC principal (auto)",
        },
      ];
    }
    return mapped;
  }

  async function handleSimular(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const validationError = validateMainForm();
    if (validationError) {
      onError(validationError);
      return;
    }
    setSubmitting(true);
    onError(null);
    onSuccess(null);
    try {
      const response = await simularOrcamento(role, {
        cliente_id: clienteId ? Number(clienteId) : undefined,
        produto_final_id: Number(produtoId),
        bom_id: bomId ? Number(bomId) : undefined,
        quantidade,
        margem_lucro_pct: margemLucroPct.trim() || undefined,
        custo_indireto_fixo: custoIndiretoFixo,
        custo_indireto_pct: custoIndiretoPct,
        operacoes: buildOperacoesPayload(),
      });
      setSimulacao(response);
      onSuccess("Simulacao de custo executada com sucesso.");
    } catch (error) {
      onError(extractErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSimularPdf(): Promise<void> {
    if (!pdfCentroId) {
      onError("Selecione o centro de trabalho para leitura automatica do PDF.");
      return;
    }
    if (!pdfFile) {
      onError("Selecione um arquivo PDF de desenho tecnico.");
      return;
    }
    setSubmitting(true);
    onError(null);
    onSuccess(null);
    try {
      const response = await simularOrcamentoPorPdf(role, {
        centro_trabalho_id: Number(pdfCentroId),
        file: pdfFile,
        margem_lucro_pct: margemLucroPct.trim() || undefined,
        custo_indireto_fixo: custoIndiretoFixo,
        custo_indireto_pct: custoIndiretoPct,
        quantidade_override: pdfQuantidadeOverride ? Number(pdfQuantidadeOverride) : undefined,
      });
      setPdfSimulacao(response);
      setQuantidade(String(response.leitura.quantidade_considerada));
      const diametrosFromPdf = response.leitura.diametros_mm
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value) && value > 0);
      if (diametrosFromPdf.length > 0) {
        const majorDiametro = Math.max(...diametrosFromPdf);
        setPieceDiametroMm(String(majorDiametro));
      }
      const comprimentoFromPdf = Number(response.leitura.comprimento_mm);
      if (Number.isFinite(comprimentoFromPdf) && comprimentoFromPdf > 0) {
        setPieceComprimentoMm(String(comprimentoFromPdf));
      }
      const cicloInferidoMin = (() => {
        const horas = Number(response.custos.horas_maquina_estimadas_unit);
        if (!Number.isFinite(horas) || horas <= 0) {
          return "8.00";
        }
        return (horas * 60).toFixed(2);
      })();
      setOperacoes((prev) => {
        if (prev.length === 0) {
          return [
            {
              centro_trabalho_id: Number(pdfCentroId),
              setup_min: "0",
              ciclo_min: cicloInferidoMin,
              descricao: "Usinagem CNC principal",
            },
          ];
        }
        const next = [...prev];
        const first = {
          ...next[0],
          centro_trabalho_id: Number(pdfCentroId),
          ciclo_min:
            !next[0].ciclo_min || Number(next[0].ciclo_min) <= 0
              ? cicloInferidoMin
              : next[0].ciclo_min,
          descricao: next[0].descricao.trim() || "Usinagem CNC principal",
        };
        next[0] = first;
        return next;
      });
      onSuccess("Leitura automatica do PDF concluida e custo estimado.");
    } catch (error) {
      onError(extractErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCriarOrcamento(): Promise<void> {
    const validationError = validateMainForm();
    if (validationError) {
      onError(validationError);
      return;
    }
    setSubmitting(true);
    onError(null);
    onSuccess(null);
    try {
      const created = await criarOrcamento(role, {
        codigo: codigo.trim() || undefined,
        referencia_projeto: referenciaProjeto.trim() || undefined,
        cliente_id: clienteId ? Number(clienteId) : undefined,
        produto_final_id: Number(produtoId),
        bom_id: bomId ? Number(bomId) : undefined,
        quantidade,
        margem_lucro_pct: margemLucroPct.trim() || undefined,
        custo_indireto_fixo: custoIndiretoFixo,
        custo_indireto_pct: custoIndiretoPct,
        observacao: observacao.trim() || undefined,
        operacoes: buildOperacoesPayload(),
      });
      setSelectedOrcamentoId(created.id);
      setSelectedOrcamento(created);
      setSearchApplied(created.codigo);
      setSearchInput(created.codigo);
      setShowSavedModule(true);
      setPage(1);
      await loadOrcamentos();
      onSuccess(`Orcamento ${created.codigo} criado com sucesso.`);
    } catch (error) {
      onError(extractErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSelectOrcamento(orcamentoId: number): Promise<void> {
    setLoadingDetail(true);
    setSelectedOrcamentoId(orcamentoId);
    setShowSavedModule(true);
    onError(null);
    try {
      const detail = await getOrcamento(role, orcamentoId);
      setSelectedOrcamento(detail);
    } catch (error) {
      onError(extractErrorMessage(error));
    } finally {
      setLoadingDetail(false);
    }
  }

  async function handleUploadAnexo(): Promise<void> {
    if (!selectedOrcamento?.id || !fileToUpload) {
      onError("Selecione um orcamento e um arquivo para envio.");
      return;
    }
    setSubmitting(true);
    onError(null);
    onSuccess(null);
    try {
      await uploadOrcamentoAnexo(role, selectedOrcamento.id, fileToUpload, fileObs);
      const refreshed = await getOrcamento(role, selectedOrcamento.id);
      setSelectedOrcamento(refreshed);
      setFileToUpload(null);
      setFileObs("");
      onSuccess("Anexo tecnico enviado com sucesso.");
    } catch (error) {
      onError(extractErrorMessage(error));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDownloadAnexo(anexoId: number): Promise<void> {
    onError(null);
    onSuccess(null);
    try {
      const payload = await downloadOrcamentoAnexo(role, anexoId);
      const url = URL.createObjectURL(payload.blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = payload.fileName;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      onSuccess("Download do anexo iniciado.");
    } catch (error) {
      onError(extractErrorMessage(error));
    }
  }

  function addOperacao(): void {
    setOperacoes((prev) => [
      ...prev,
      { centro_trabalho_id: "", setup_min: "0", ciclo_min: "0", descricao: "" },
    ]);
  }

  function removeOperacao(index: number): void {
    setOperacoes((prev) => prev.filter((_, idx) => idx !== index));
  }

  function updateOperacao(index: number, key: keyof OperacaoDraft, value: string): void {
    setOperacoes((prev) =>
      prev.map((item, idx) =>
        idx === index
          ? {
              ...item,
              [key]: key === "centro_trabalho_id" ? (value ? Number(value) : "") : value,
            }
          : item
      )
    );
  }

  function upsertPresetNote(
    previous: string,
    machineName: string,
    materialName: string,
    operationName: string
  ): string {
    const filtered = previous
      .split("\n")
      .map((line) => line.trimEnd())
      .filter(
        (line) =>
          line.trim() !== "" &&
          !line.startsWith(PRESET_NOTE_TAG) &&
          !line.startsWith(AUTO_STRATEGY_NOTE_TAG)
      );
    const note = `${PRESET_NOTE_TAG} ${machineName} | ${materialName} | ${operationName}`;
    return [...filtered, note].join("\n");
  }

  function handleApplyCncPreset(): void {
    if (!presetMachine || !presetMaterial || !presetOperation) {
      onError("Nao foi possivel aplicar preset CNC. Selecione maquina, material e operacao.");
      return;
    }
    if (centros.length === 0) {
      onError("Cadastre ao menos um centro de trabalho para aplicar o preset CNC.");
      return;
    }

    const currentCenter =
      operacaoPrincipal.centro_trabalho_id !== ""
        ? centros.find((centro) => centro.id === Number(operacaoPrincipal.centro_trabalho_id)) ?? null
        : null;
    const suggestedCenter = suggestCentroForMachinePreset(
      centros,
      presetMachine,
      manufacturerProfile
    );
    const chosenCenter = currentCenter ?? suggestedCenter;

    if (!chosenCenter) {
      onError("Nao foi encontrado centro compativel para o preset escolhido.");
      return;
    }

    const suggestedSetup = calculateSetupMinFromPreset(
      presetMachine,
      presetOperation,
      chosenCenter,
      manufacturerProfile
    );
    const suggestedMargin = Math.max(
      presetMachine.margem_lucro_pct,
      presetMaterial.margem_lucro_pct,
      presetOperation.margem_lucro_pct
    );
    const suggestedIndirect = Math.max(
      presetMachine.custo_indireto_pct,
      presetOperation.custo_indireto_pct
    );

    setOperacoes((prev) => {
      const next = prev.length > 0 ? [...prev] : [{ centro_trabalho_id: "", setup_min: "0", ciclo_min: "0", descricao: "" }];
      const first = next[0] ?? { centro_trabalho_id: "", setup_min: "0", ciclo_min: "0", descricao: "" };
      next[0] = {
        ...first,
        centro_trabalho_id: chosenCenter.id,
        setup_min: suggestedSetup,
        ciclo_min: presetCycleMin,
        descricao: `${presetOperation.nome} - ${presetMaterial.nome}`,
      };
      return next;
    });

    if (!pdfCentroId) {
      setPdfCentroId(chosenCenter.id);
    }
    if (!margemLucroPct.trim() || Number(margemLucroPct) <= 0) {
      setMargemLucroPct(String(suggestedMargin));
    }
    setCustoIndiretoPct(String(suggestedIndirect));
    setObservacao((prev) =>
      upsertPresetNote(
        prev,
        `${presetMachine.nome} / ${manufacturerProfile?.nome ?? "fabricante padrao"}`,
        presetMaterial.nome,
        `${presetOperation.nome} / ${pieceFamily?.nome ?? pieceType}`
      )
    );
    onError(null);
    onSuccess(
      `Preset CNC aplicado: ${presetOperation.nome} em ${presetMaterial.nome} (${chosenCenter.codigo}) usando ${manufacturerProfile?.nome ?? "perfil base"}.`
    );
  }

  function handleApplyAutoStrategy(): void {
    if (!presetMachine || !presetMaterial || !autoStrategyPlan) {
      onError("Nao foi possivel gerar estrategia automatica com os parametros atuais.");
      return;
    }
    if (centros.length === 0) {
      onError("Cadastre ao menos um centro de trabalho para aplicar estrategia automatica.");
      return;
    }

    const suggestedCenter = suggestCentroForMachinePreset(
      centros,
      presetMachine,
      manufacturerProfile
    );
    if (!suggestedCenter) {
      onError("Nao foi encontrado centro compativel para estrategia automatica.");
      return;
    }

    const nextOperations: OperacaoDraft[] = autoStrategyPlan.operations.map((operation) => ({
      centro_trabalho_id: suggestedCenter.id,
      setup_min: operation.setupMin,
      ciclo_min: operation.cicloMin,
      descricao: operation.descricao,
    }));
    setOperacoes(nextOperations);

    if (!pdfCentroId) {
      setPdfCentroId(suggestedCenter.id);
    }
    setMargemLucroPct(String(autoStrategyPlan.suggestedMarginPct));
    setCustoIndiretoPct(String(autoStrategyPlan.suggestedIndirectPct));
    setObservacao((prev) => {
      const filtered = prev
        .split("\n")
        .map((line) => line.trimEnd())
        .filter(
          (line) =>
            line.trim() !== "" &&
            !line.startsWith(PRESET_NOTE_TAG) &&
            !line.startsWith(AUTO_STRATEGY_NOTE_TAG)
        );
      const autoNote = `${AUTO_STRATEGY_NOTE_TAG} ${pieceFamily?.nome ?? pieceType} | D=${pieceDiametroMm || "-"} mm | L=${pieceComprimentoMm || "-"} mm | furos~${autoStrategyPlan.furosEstimados}`;
      const presetNote = `${PRESET_NOTE_TAG} ${presetMachine.nome} / ${manufacturerProfile?.nome ?? "-"} | ${presetMaterial.nome} | estrategia ${autoStrategyPlan.operations.length} operacoes`;
      return [...filtered, autoNote, presetNote].join("\n");
    });
    onError(null);
    onSuccess(
      `Estrategia automatica aplicada para ${pieceFamily?.nome ?? pieceType} em ${suggestedCenter.codigo}.`
    );
  }

  if (role === "operador") {
    return (
      <main className="mx-auto max-w-7xl px-4 py-4">
        <section className="rounded-lg border border-amber-600/40 bg-amber-950/20 p-4 text-amber-100">
          <h2 className="text-base font-semibold">Acesso restrito ao Gerador de Orcamentos</h2>
          <p className="mt-2 text-sm text-amber-100/90">
            O perfil <strong>operador</strong> nao possui permissao para este modulo.
            Troque o perfil no topo para <strong>pcp</strong>, <strong>compras</strong> ou{" "}
            <strong>admin</strong>.
          </p>
        </section>
      </main>
    );
  }

  return (
    <main className="industrial-panel mx-auto grid max-w-7xl gap-4 px-4 py-4 lg:grid-cols-[1.2fr_1fr]">
      <section className="space-y-4">
        <section className="rounded-lg border border-cyan-900/40 bg-slate-900/85 p-4 shadow-lg shadow-cyan-950/20">
          <div className="industrial-accent-strip mb-4" />
          <h2 className="mb-3 text-lg font-semibold">Gerador de Orcamentos</h2>
          <p className="mb-4 text-sm text-slate-300">
            Fluxo rapido para centro de usinagem (tarugo de aco/aluminio): leia o PDF,
            revise o custo e so depois, se quiser, salve o orcamento completo.
          </p>
          <div className="mb-4 grid gap-2 md:grid-cols-3">
            <div className="rounded-md border border-slate-700 bg-slate-950/80 px-3 py-2 text-xs text-slate-300">
              <p className="font-semibold text-cyan-300">PASSO 1</p>
              <p>Selecionar centro CNC e desenho tecnico (PDF).</p>
            </div>
            <div className="rounded-md border border-slate-700 bg-slate-950/80 px-3 py-2 text-xs text-slate-300">
              <p className="font-semibold text-cyan-300">PASSO 2</p>
              <p>Sistema estima tempo, material e preco sugerido.</p>
            </div>
            <div className="rounded-md border border-slate-700 bg-slate-950/80 px-3 py-2 text-xs text-slate-300">
              <p className="font-semibold text-cyan-300">PASSO 3</p>
              <p>Opcional: salvar orcamento e anexar desenho.</p>
            </div>
          </div>
          <div className="mb-4 rounded-lg border border-cyan-700/40 bg-cyan-950/20 p-3">
            <h3 className="mb-1 text-sm font-semibold text-cyan-200">
              Pre-definicoes CNC de mercado (V3)
            </h3>
            <p className="mb-3 text-xs text-cyan-100/85">
              V3: biblioteca por fabricante + familia de peca + estrategia automatica multi-operacao.
            </p>
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-5">
              <label className="grid gap-1 text-xs">
                <span className="text-slate-300">Fabricante / linha</span>
                <select
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={manufacturerProfileId}
                  onChange={(event) => setManufacturerProfileId(event.target.value)}
                >
                  {CNC_MANUFACTURER_PROFILES.map((maker) => (
                    <option key={maker.id} value={maker.id}>
                      {maker.nome}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs">
                <span className="text-slate-300">Perfil de maquina</span>
                <select
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={presetMachineId}
                  onChange={(event) => setPresetMachineId(event.target.value)}
                >
                  {CNC_MACHINE_PRESETS.map((machine) => (
                    <option key={machine.id} value={machine.id}>
                      {machine.nome}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs">
                <span className="text-slate-300">Familia de peca</span>
                <select
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={pieceFamilyId}
                  onChange={(event) => setPieceFamilyId(event.target.value)}
                >
                  {CNC_PIECE_FAMILIES.map((family) => (
                    <option key={family.id} value={family.id}>
                      {family.nome}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs">
                <span className="text-slate-300">Material</span>
                <select
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={presetMaterialId}
                  onChange={(event) => setPresetMaterialId(event.target.value)}
                >
                  {CNC_MATERIAL_PRESETS.map((material) => (
                    <option key={material.id} value={material.id}>
                      {material.nome} ({material.liga_ref})
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs">
                <span className="text-slate-300">Operacao padrao</span>
                <select
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={presetOperationId}
                  onChange={(event) => setPresetOperationId(event.target.value)}
                >
                  {CNC_OPERATION_PRESETS.map((operation) => (
                    <option key={operation.id} value={operation.id}>
                      {operation.nome}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="rounded-md border border-cyan-600 px-3 py-2 text-sm text-cyan-100 hover:bg-cyan-900/25"
                onClick={handleApplyCncPreset}
              >
                Aplicar preset CNC
              </button>
              <p className="text-xs text-cyan-100/90">
                Ciclo sug.: <strong>{formatNumber(presetCycleMin, 2)} min</strong> | Setup sug.:{" "}
                <strong>
                  {presetMachine && presetOperation
                    ? formatNumber(
                        calculateSetupMinFromPreset(
                          presetMachine,
                          presetOperation,
                          undefined,
                          manufacturerProfile
                        ),
                        2
                      )
                    : "-"}{" "}
                  min
                </strong>
              </p>
            </div>
            <div className="mt-3 rounded border border-cyan-900/40 bg-slate-950/70 p-3">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-cyan-200">
                Estrategia automatica por tipo de peca
              </h4>
              <p className="mb-2 text-xs text-cyan-100/85">
                Familia ativa: <strong>{pieceFamily?.nome ?? "-"}</strong> | Fabricante:{" "}
                <strong>{manufacturerProfile?.nome ?? "-"}</strong>
              </p>
              <div className="grid gap-2 md:grid-cols-3">
                <label className="grid gap-1 text-xs">
                  <span className="text-slate-300">Tipo de peca</span>
                  <select
                    className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                    value={pieceType}
                    onChange={(event) => setPieceType(event.target.value as CncPieceType)}
                  >
                    <option value="EIXO">Eixo</option>
                    <option value="FLANGE">Flange</option>
                    <option value="BLOCO">Bloco</option>
                  </select>
                </label>
                <label className="grid gap-1 text-xs">
                  <span className="text-slate-300">Diametro / largura (mm)</span>
                  <input
                    type="number"
                    min="1"
                    step="0.1"
                    className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                    value={pieceDiametroMm}
                    onChange={(event) => setPieceDiametroMm(event.target.value)}
                    placeholder="Ex.: 60"
                  />
                </label>
                <label className="grid gap-1 text-xs">
                  <span className="text-slate-300">Comprimento (mm)</span>
                  <input
                    type="number"
                    min="1"
                    step="0.1"
                    className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                    value={pieceComprimentoMm}
                    onChange={(event) => setPieceComprimentoMm(event.target.value)}
                    placeholder="Ex.: 180"
                  />
                </label>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="rounded-md border border-cyan-700 px-3 py-2 text-sm text-cyan-100 hover:bg-cyan-900/25"
                  onClick={() => {
                    if (!pieceFamily) {
                      return;
                    }
                    setPieceType(pieceFamily.pieceType);
                    setPieceDiametroMm(String(pieceFamily.default_diametro_mm));
                    setPieceComprimentoMm(String(pieceFamily.default_comprimento_mm));
                    onSuccess(`Dimensoes padrao aplicadas para a familia ${pieceFamily.nome}.`);
                  }}
                >
                  Aplicar dimensoes padrao da familia
                </button>
                <button
                  type="button"
                  className="rounded-md border border-emerald-600 px-3 py-2 text-sm text-emerald-100 hover:bg-emerald-900/25"
                  onClick={handleApplyAutoStrategy}
                >
                  Aplicar estrategia automatica (3 operacoes)
                </button>
                {autoStrategyPlan && (
                  <p className="text-xs text-emerald-100/90">
                    Fator dim.: <strong>{formatNumber(autoStrategyPlan.dimensionFactor, 2)}</strong> |
                    Furos estimados: <strong>{autoStrategyPlan.furosEstimados}</strong> | Margem:{" "}
                    <strong>{formatNumber(autoStrategyPlan.suggestedMarginPct, 0)}%</strong> |
                    Indireto: <strong>{formatNumber(autoStrategyPlan.suggestedIndirectPct, 0)}%</strong>
                  </p>
                )}
              </div>
              {autoStrategyPlan && (
                <div className="mt-2 grid gap-1 rounded border border-slate-800 bg-slate-900/80 px-3 py-2 text-xs text-slate-300 md:grid-cols-3">
                  {autoStrategyPlan.operations.map((operation) => (
                    <div key={operation.operationPresetId} className="rounded border border-slate-800 px-2 py-1">
                      <p className="font-semibold text-slate-200">{operation.operationNome}</p>
                      <p>
                        Ciclo: {formatNumber(operation.cicloMin, 2)} min | Setup:{" "}
                        {formatNumber(operation.setupMin, 2)} min
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            {presetMachine && presetMaterial && presetOperation && (
              <div className="mt-2 rounded border border-cyan-900/40 bg-slate-950/60 px-3 py-2 text-xs text-slate-300">
                <p>
                  {presetMachine.descricao} | Fabricante:{" "}
                  {manufacturerProfile?.fabricante ?? "-"} ({manufacturerProfile?.linha_referencia ?? "-"}) | Familia:{" "}
                  {pieceFamily?.nome ?? "-"} | Material {presetMaterial.liga_ref} (Vc{" "}
                  {presetMaterial.vc_referencia_m_min} m/min, fz{" "}
                  {presetMaterial.fz_referencia_mm_dente} mm/dente) | Operacao:{" "}
                  {presetOperation.descricao}
                </p>
              </div>
            )}
          </div>
          {loadingCatalogos && <p className="text-sm text-slate-400">Carregando cadastros...</p>}

          <div className="mb-4 rounded-lg border border-violet-700/40 bg-violet-900/10 p-3">
            <h3 className="mb-2 text-sm font-semibold text-violet-200">
              Leitura automatica de desenho tecnico (PDF)
            </h3>
            <p className="mb-3 text-xs text-slate-400">
              Fluxo PDF-first: envie o desenho tecnico e o sistema infere material/dimensoes para
              estimar custo automaticamente.
            </p>
            <div className="grid gap-2 md:grid-cols-2">
              <label className="grid gap-1 text-xs">
                <span className="text-slate-400">Centro de trabalho para estimativa</span>
                <select
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={pdfCentroId}
                  onChange={(event) => setPdfCentroId(event.target.value ? Number(event.target.value) : "")}
                >
                  <option value="">Selecione</option>
                  {centros.map((centro) => (
                    <option key={centro.id} value={centro.id}>
                      {centro.codigo} - {centro.nome}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs">
                <span className="text-slate-400">Quantidade (override opcional)</span>
                <input
                  type="number"
                  min="1"
                  step="1"
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={pdfQuantidadeOverride}
                  onChange={(event) => setPdfQuantidadeOverride(event.target.value)}
                  placeholder="Se vazio, usa quantidade inferida no PDF"
                />
              </label>
            </div>
            <div className="mt-2 grid gap-2">
              <input
                type="file"
                accept=".pdf,application/pdf"
                onChange={(event) => setPdfFile(event.target.files?.[0] ?? null)}
                className="text-xs"
              />
              <button
                type="button"
                className="rounded-md border border-violet-600 px-3 py-2 text-sm text-violet-100 hover:bg-violet-900/20 disabled:opacity-50"
                onClick={() => void handleSimularPdf()}
                disabled={submitting || !pdfFile || !pdfCentroId}
              >
                Ler PDF e calcular custo automaticamente
              </button>
            </div>

            {pdfSimulacao && (
              <div className="mt-3 space-y-2">
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  <Metric
                    label="Material inferido"
                    value={pdfSimulacao.leitura.material_inferido || "Nao identificado"}
                  />
                  <Metric
                    label="Confianca"
                    value={pdfSimulacao.leitura.confianca}
                  />
                  <Metric
                    label="Qtd considerada"
                    value={String(pdfSimulacao.leitura.quantidade_considerada)}
                  />
                  <Metric
                    label="Preco sugerido"
                    value={`R$ ${formatNumber(pdfSimulacao.custos.preco_venda_sugerido, 2)}`}
                  />
                </div>
                <p className="text-xs text-slate-300">
                  Diametros:{" "}
                  {pdfSimulacao.leitura.diametros_mm.length > 0
                    ? pdfSimulacao.leitura.diametros_mm.map((d) => formatNumber(d, 3)).join(", ")
                    : "nao identificados"}
                  {" | "}
                  Comprimento:{" "}
                  {pdfSimulacao.leitura.comprimento_mm
                    ? `${formatNumber(pdfSimulacao.leitura.comprimento_mm, 3)} mm`
                    : "nao identificado"}
                </p>
                {pdfSimulacao.premissas.length > 0 && (
                  <ul className="list-disc space-y-1 pl-5 text-xs text-amber-200/90">
                    {pdfSimulacao.premissas.map((premissa, index) => (
                      <li key={`premissa-${index}`}>{premissa}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          <form className="grid gap-3" onSubmit={handleSimular}>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="grid gap-1 text-sm">
                <span className="text-slate-400">Produto final (obrigatorio)</span>
                <select
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={produtoId}
                  onChange={(event) => setProdutoId(event.target.value ? Number(event.target.value) : "")}
                >
                  <option value="">Selecione</option>
                  {produtos.map((produto) => (
                    <option key={produto.id} value={produto.id}>
                      {produto.codigo} - {produto.descricao}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-sm">
                <span className="text-slate-400">Quantidade (obrigatorio)</span>
                <input
                  type="number"
                  min="0.001"
                  step="0.001"
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={quantidade}
                  onChange={(event) => setQuantidade(event.target.value)}
                />
              </label>
              <label className="grid gap-1 text-sm">
                <span className="text-slate-400">Centro de usinagem principal</span>
                <select
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={operacaoPrincipal.centro_trabalho_id}
                  onChange={(event) => updateOperacao(0, "centro_trabalho_id", event.target.value)}
                >
                  <option value="">Selecione</option>
                  {centros.map((centro) => (
                    <option key={centro.id} value={centro.id}>
                      {centro.codigo} - {centro.nome}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-sm">
                <span className="text-slate-400">Ciclo estimado (min por peca)</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={operacaoPrincipal.ciclo_min}
                  onChange={(event) => updateOperacao(0, "ciclo_min", event.target.value)}
                  placeholder={suggestedCycleMin}
                />
              </label>
              <label className="grid gap-1 text-sm">
                <span className="text-slate-400">Setup do lote (min)</span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={operacaoPrincipal.setup_min}
                  onChange={(event) => updateOperacao(0, "setup_min", event.target.value)}
                />
              </label>
              <div className="grid content-end text-xs text-slate-300">
                <button
                  type="button"
                  className="rounded-md border border-cyan-700/60 bg-cyan-900/10 px-3 py-2 text-left text-cyan-100 hover:bg-cyan-900/20"
                  onClick={() => {
                    if (!pdfCentroId) {
                      onError("Leia um PDF primeiro para aplicar centro/tempo automaticamente.");
                      return;
                    }
                    updateOperacao(0, "centro_trabalho_id", String(pdfCentroId));
                    updateOperacao(0, "ciclo_min", suggestedCycleMin);
                    if (!operacaoPrincipal.descricao.trim()) {
                      updateOperacao(0, "descricao", "Usinagem CNC principal");
                    }
                    onSuccess("Centro e ciclo principal preenchidos com base na leitura do PDF.");
                  }}
                >
                  Aplicar parametros sugeridos pelo PDF
                </button>
              </div>
            </div>

            <details className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
              <summary className="cursor-pointer text-sm font-medium text-slate-200">
                Campos opcionais e custos avancados
              </summary>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <label className="grid gap-1 text-sm">
                  <span className="text-slate-400">Codigo do orcamento (opcional)</span>
                  <input
                    className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                    value={codigo}
                    onChange={(event) => setCodigo(event.target.value)}
                    placeholder="ORC-2026-001"
                  />
                </label>
                <label className="grid gap-1 text-sm">
                  <span className="text-slate-400">Referencia de projeto</span>
                  <input
                    className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                    value={referenciaProjeto}
                    onChange={(event) => setReferenciaProjeto(event.target.value)}
                    placeholder="PROJ-MAQ-CNC-001"
                  />
                </label>
                <label className="grid gap-1 text-sm">
                  <span className="text-slate-400">Cliente (opcional)</span>
                  <select
                    className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                    value={clienteId}
                    onChange={(event) => setClienteId(event.target.value ? Number(event.target.value) : "")}
                  >
                    <option value="">Nao informado</option>
                    {clientes.map((cliente) => (
                      <option key={cliente.id} value={cliente.id}>
                        {cliente.codigo} - {cliente.razao_social}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="grid gap-1 text-sm">
                  <span className="text-slate-400">BOM (opcional)</span>
                  <select
                    className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                    value={bomId}
                    onChange={(event) => setBomId(event.target.value ? Number(event.target.value) : "")}
                  >
                    <option value="">Resolver automaticamente</option>
                    {boms.map((bom) => (
                      <option key={bom.id} value={bom.id}>
                        ID {bom.id} - Versao {bom.versao} ({bom.status})
                      </option>
                    ))}
                  </select>
                  {loadingBoms && <span className="text-xs text-slate-500">Carregando BOMs...</span>}
                </label>
                <label className="grid gap-1 text-sm">
                  <span className="text-slate-400">
                    Margem lucro % (padrao: {formatNumber(produtoSelecionado?.margem_lucro_padrao_pct ?? "-", 2)})
                  </span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                    value={margemLucroPct}
                    onChange={(event) => setMargemLucroPct(event.target.value)}
                    placeholder="Ex.: 30"
                  />
                </label>
                <label className="grid gap-1 text-sm">
                  <span className="text-slate-400">Custo indireto fixo (R$)</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                    value={custoIndiretoFixo}
                    onChange={(event) => setCustoIndiretoFixo(event.target.value)}
                  />
                </label>
                <label className="grid gap-1 text-sm">
                  <span className="text-slate-400">Custo indireto %</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                    value={custoIndiretoPct}
                    onChange={(event) => setCustoIndiretoPct(event.target.value)}
                  />
                </label>
              </div>
              <label className="mt-3 grid gap-1 text-sm">
                <span className="text-slate-400">Observacao</span>
                <textarea
                  className="min-h-20 rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                  value={observacao}
                  onChange={(event) => setObservacao(event.target.value)}
                  placeholder="Informacoes tecnicas adicionais do projeto..."
                />
              </label>
            </details>

            <details className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
              <summary className="cursor-pointer text-sm font-medium text-slate-200">
                Operacoes secundarias (opcional)
              </summary>
              <div className="mt-3 space-y-2">
                <div className="flex justify-end">
                  <button
                    type="button"
                    className="rounded border border-slate-700 px-2 py-1 text-xs hover:bg-slate-800"
                    onClick={addOperacao}
                  >
                    + Adicionar operacao secundaria
                  </button>
                </div>
                {operacoes.length === 1 && (
                  <p className="text-xs text-slate-500">
                    Somente operacao principal ativa. Adicione outras somente se necessario.
                  </p>
                )}
                {operacoes.slice(1).map((op, index) => {
                  const realIndex = index + 1;
                  return (
                    <div
                      key={`op-${realIndex}`}
                      className="grid gap-2 rounded border border-slate-800 p-2 md:grid-cols-12"
                    >
                      <label className="grid gap-1 text-xs md:col-span-4">
                        <span className="text-slate-400">Centro</span>
                        <select
                          className="rounded-md border border-slate-700 bg-slate-900 px-2 py-2"
                          value={op.centro_trabalho_id}
                          onChange={(event) =>
                            updateOperacao(realIndex, "centro_trabalho_id", event.target.value)
                          }
                        >
                          <option value="">Selecione</option>
                          {centros.map((centro) => (
                            <option key={centro.id} value={centro.id}>
                              {centro.codigo} - {centro.nome}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="grid gap-1 text-xs md:col-span-2">
                        <span className="text-slate-400">Setup (min)</span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          className="rounded-md border border-slate-700 bg-slate-900 px-2 py-2"
                          value={op.setup_min}
                          onChange={(event) => updateOperacao(realIndex, "setup_min", event.target.value)}
                        />
                      </label>
                      <label className="grid gap-1 text-xs md:col-span-2">
                        <span className="text-slate-400">Ciclo (min)</span>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          className="rounded-md border border-slate-700 bg-slate-900 px-2 py-2"
                          value={op.ciclo_min}
                          onChange={(event) => updateOperacao(realIndex, "ciclo_min", event.target.value)}
                        />
                      </label>
                      <label className="grid gap-1 text-xs md:col-span-3">
                        <span className="text-slate-400">Descricao</span>
                        <input
                          className="rounded-md border border-slate-700 bg-slate-900 px-2 py-2"
                          value={op.descricao}
                          onChange={(event) => updateOperacao(realIndex, "descricao", event.target.value)}
                          placeholder="Ex.: Furo profundo"
                        />
                      </label>
                      <div className="grid content-end md:col-span-1">
                        <button
                          type="button"
                          className="rounded border border-rose-700 px-2 py-2 text-xs text-rose-200 hover:bg-rose-900/30"
                          onClick={() => removeOperacao(realIndex)}
                        >
                          Remover
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </details>

            <div className="flex flex-wrap gap-2">
              <button
                type="submit"
                className="rounded-md bg-cyan-600 px-4 py-2 text-sm font-medium hover:bg-cyan-500 disabled:opacity-50"
                disabled={submitting}
              >
                Simular custo rapido
              </button>
              <button
                type="button"
                className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
                disabled={submitting}
                onClick={() => void handleCriarOrcamento()}
              >
                Salvar orcamento completo
              </button>
            </div>
          </form>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-300">Resultado da simulacao</h3>
          {!simulacao && <p className="text-sm text-slate-500">Execute uma simulacao para visualizar custos.</p>}
          {simulacao && (
            <div className="space-y-3">
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <Metric label="Custo material" value={`R$ ${formatNumber(simulacao.custo_material_total, 2)}`} />
                <Metric label="Custo maquina" value={`R$ ${formatNumber(simulacao.custo_maquina_total, 2)}`} />
                <Metric label="Custo indireto" value={`R$ ${formatNumber(simulacao.custo_indireto_total, 2)}`} />
                <Metric label="Preco venda" value={`R$ ${formatNumber(simulacao.preco_venda, 2)}`} />
              </div>

              <div className="grid gap-3 lg:grid-cols-2">
                <div className="rounded border border-slate-800 bg-slate-950 p-3">
                  <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">Materiais</h4>
                  <div className="max-h-52 overflow-auto">
                    <table className="min-w-full text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 text-left text-slate-400">
                          <th className="px-2 py-1">Codigo</th>
                          <th className="px-2 py-1">Qtd</th>
                          <th className="px-2 py-1">Custo total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {simulacao.materiais.map((item) => (
                          <tr key={item.insumo_id} className="border-b border-slate-900">
                            <td className="px-2 py-1">{item.codigo}</td>
                            <td className="px-2 py-1">{formatNumber(item.quantidade_total, 3)}</td>
                            <td className="px-2 py-1">R$ {formatNumber(item.custo_total, 2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="rounded border border-slate-800 bg-slate-950 p-3">
                  <h4 className="mb-2 text-xs font-semibold uppercase text-slate-400">Operacoes</h4>
                  <div className="max-h-52 overflow-auto">
                    <table className="min-w-full text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 text-left text-slate-400">
                          <th className="px-2 py-1">Centro</th>
                          <th className="px-2 py-1">Tempo (h)</th>
                          <th className="px-2 py-1">Custo</th>
                        </tr>
                      </thead>
                      <tbody>
                        {simulacao.operacoes.map((item) => (
                          <tr key={`${item.centro_trabalho_id}-${item.sequencia}`} className="border-b border-slate-900">
                            <td className="px-2 py-1">{item.codigo_centro}</td>
                            <td className="px-2 py-1">{formatNumber(item.tempo_total_horas, 3)}</td>
                            <td className="px-2 py-1">R$ {formatNumber(item.custo_operacao, 2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          )}
        </section>
      </section>

      <section className="space-y-4">
        <section className="rounded-lg border border-amber-700/40 bg-amber-950/15 p-4">
          <h3 className="mb-1 text-sm font-semibold text-amber-200">Modo operacao para centro CNC</h3>
          <p className="mb-3 text-xs text-amber-100/80">
            Para cotacao rapida de peca usinada em tarugo, use apenas os campos da esquerda.
            Lista de orcamentos salvos e anexos fica em gestao completa.
          </p>
          <button
            type="button"
            className="rounded border border-amber-500/60 px-3 py-2 text-xs font-medium text-amber-100 hover:bg-amber-900/30"
            onClick={() => setShowSavedModule((prev) => !prev)}
          >
            {showSavedModule ? "Ocultar gestao completa" : "Mostrar gestao completa"}
          </button>
        </section>

        {showSavedModule && (
          <>
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-300">Orcamentos salvos</h3>
          <div className="mb-3 grid gap-2">
            <div className="flex gap-2">
              <input
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Buscar por codigo, projeto ou produto"
              />
              <button
                className="rounded border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800"
                onClick={() => {
                  setPage(1);
                  setSearchApplied(searchInput.trim());
                }}
              >
                Buscar
              </button>
            </div>
            <select
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(event.target.value);
                setPage(1);
              }}
            >
              {ORCAMENTO_STATUS_FILTERS.map((status) => (
                <option key={status || "todos"} value={status}>
                  {status || "TODOS"}
                </option>
              ))}
            </select>
          </div>

          <div className="mb-2 flex items-center justify-between text-xs text-slate-400">
            <span>
              Total: {total} | Pag. {page}/{totalPages}
            </span>
            <div className="flex gap-2">
              <button
                className="rounded border border-slate-700 px-2 py-1 hover:bg-slate-800 disabled:opacity-50"
                onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                disabled={page <= 1}
              >
                Anterior
              </button>
              <button
                className="rounded border border-slate-700 px-2 py-1 hover:bg-slate-800 disabled:opacity-50"
                onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                disabled={page >= totalPages}
              >
                Proxima
              </button>
            </div>
          </div>

          <div className="max-h-72 space-y-2 overflow-auto pr-1">
            {loadingOrcamentos && <p className="text-sm text-slate-400">Carregando orcamentos...</p>}
            {!loadingOrcamentos && orcamentos.length === 0 && (
              <p className="text-sm text-slate-500">Nenhum orcamento encontrado.</p>
            )}
            {orcamentos.map((item) => (
              <button
                key={item.id}
                className={`w-full rounded-lg border px-3 py-3 text-left transition ${
                  selectedOrcamentoId === item.id
                    ? "border-sky-500 bg-sky-500/10"
                    : "border-slate-800 bg-slate-950 hover:border-slate-600"
                }`}
                onClick={() => void handleSelectOrcamento(item.id)}
              >
                <div className="mb-1 flex items-center justify-between">
                  <span className="font-medium">{item.codigo}</span>
                  <span className={`rounded border px-2 py-0.5 text-xs ${statusBadge(item.status)}`}>
                    {item.status}
                  </span>
                </div>
                <p className="text-xs text-slate-300">
                  Projeto: {item.referencia_projeto || "-"} | Produto: {item.produto_codigo}
                </p>
                <p className="text-xs text-slate-400">
                  Versao atual: {item.versao_atual ?? "-"} | Preco:{" "}
                  {item.preco_venda_atual ? `R$ ${formatNumber(item.preco_venda_atual, 2)}` : "-"}
                </p>
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          {!selectedOrcamentoId && (
            <p className="text-sm text-slate-500">
              Selecione um orcamento na lista para ver detalhe e anexar desenho tecnico.
            </p>
          )}
          {selectedOrcamentoId && loadingDetail && (
            <p className="text-sm text-slate-400">Carregando detalhe do orcamento...</p>
          )}
          {selectedOrcamento && (
            <div className="space-y-3">
              <div className="rounded border border-slate-800 bg-slate-950 p-3">
                <div className="mb-1 flex items-center justify-between">
                  <h4 className="font-semibold">{selectedOrcamento.codigo}</h4>
                  <span className={`rounded border px-2 py-0.5 text-xs ${statusBadge(selectedOrcamento.status)}`}>
                    {selectedOrcamento.status}
                  </span>
                </div>
                <p className="text-sm text-slate-300">{selectedOrcamento.produto_descricao}</p>
                <p className="text-xs text-slate-400">
                  Projeto: {selectedOrcamento.referencia_projeto || "-"} | Cliente:{" "}
                  {selectedOrcamento.cliente_nome || "-"}
                </p>
                <p className="text-xs text-slate-500">
                  Criado em: {formatDateTime(selectedOrcamento.created_at)}
                </p>
              </div>

              <div className="rounded border border-slate-800 bg-slate-950 p-3">
                <h5 className="mb-2 text-xs font-semibold uppercase text-slate-400">
                  Versoes do orcamento
                </h5>
                <div className="max-h-44 space-y-1 overflow-auto pr-1">
                  {selectedOrcamento.versoes.map((versao) => (
                    <div key={versao.id} className="rounded border border-slate-800 px-2 py-2 text-xs">
                      <p className="text-slate-200">
                        Versao {versao.versao} | Qtd {formatNumber(versao.quantidade, 3)} | Preco R${" "}
                        {formatNumber(versao.preco_venda, 2)}
                      </p>
                      <p className="text-slate-400">
                        Material R$ {formatNumber(versao.custo_material_total, 2)} | Maquina R${" "}
                        {formatNumber(versao.custo_maquina_total, 2)} | Indireto R${" "}
                        {formatNumber(versao.custo_indireto_total, 2)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded border border-slate-800 bg-slate-950 p-3">
                <h5 className="mb-2 text-xs font-semibold uppercase text-slate-400">
                  Anexos tecnicos (PDF/DXF/STEP)
                </h5>
                <div className="mb-3 grid gap-2">
                  <input
                    type="file"
                    accept=".pdf,.dxf,.dwg,.step,.stp,.iges,.igs,.png,.jpg,.jpeg"
                    onChange={(event) => setFileToUpload(event.target.files?.[0] ?? null)}
                    className="text-xs"
                  />
                  <input
                    className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs"
                    value={fileObs}
                    onChange={(event) => setFileObs(event.target.value)}
                    placeholder="Observacao do anexo (opcional)"
                  />
                  <button
                    className="rounded border border-violet-700 px-3 py-2 text-sm text-violet-200 hover:bg-violet-900/20 disabled:opacity-50"
                    onClick={() => void handleUploadAnexo()}
                    disabled={submitting || !fileToUpload}
                  >
                    Enviar desenho tecnico
                  </button>
                </div>

                <div className="max-h-40 space-y-1 overflow-auto pr-1">
                  {selectedOrcamento.anexos.length === 0 && (
                    <p className="text-xs text-slate-500">Nenhum anexo enviado.</p>
                  )}
                  {selectedOrcamento.anexos.map((anexo) => (
                    <div key={anexo.id} className="rounded border border-slate-800 px-2 py-2 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-slate-200">{anexo.nome_arquivo_original}</p>
                        <button
                          className="rounded border border-sky-700 px-2 py-1 text-xs text-sky-200 hover:bg-sky-900/30"
                          onClick={() => void handleDownloadAnexo(anexo.id)}
                        >
                          Baixar
                        </button>
                      </div>
                      <p className="text-slate-400">
                        {Math.max(1, Math.round(anexo.tamanho_bytes / 1024))} KB |{" "}
                        {formatDateTime(anexo.uploaded_at)}
                      </p>
                      {anexo.observacao && <p className="text-slate-400">{anexo.observacao}</p>}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>
          </>
        )}
      </section>
    </main>
  );
}
