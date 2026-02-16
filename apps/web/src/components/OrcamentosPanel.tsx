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
  uploadOrcamentoAnexo,
} from "../api";
import type {
  BomListItem,
  CentroTrabalhoCadastro,
  ClienteCadastro,
  OrcamentoDetail,
  OrcamentoListItem,
  OrcamentoOperacaoInput,
  OrcamentoSimulacao,
  ProdutoFinalCadastro,
} from "../types";
import { extractErrorMessage } from "../utils/errors";
import { formatDateTime, formatNumber, statusBadge } from "../utils/ui";
import { Metric } from "./Metric";
import type { StandardPanelProps } from "./panels/types";

const ORCAMENTO_STATUS_FILTERS = ["", "RASCUNHO", "ENVIADO", "APROVADO", "REJEITADO"] as const;

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

  const [operacoes, setOperacoes] = useState<OperacaoDraft[]>([
    { centro_trabalho_id: "", setup_min: "0", ciclo_min: "0", descricao: "" },
  ]);

  const [fileToUpload, setFileToUpload] = useState<File | null>(null);
  const [fileObs, setFileObs] = useState("");

  const totalPages = Math.max(1, Math.ceil(total / 10));

  const produtoSelecionado = useMemo(
    () => produtos.find((produto) => produto.id === produtoId) ?? null,
    [produtoId, produtos]
  );

  useEffect(() => {
    if (!isActive) {
      return;
    }
    void loadCatalogos();
  }, [isActive, role]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isActive) {
      return;
    }
    void loadOrcamentos();
  }, [isActive, role, page, searchApplied, statusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!produtoId || !isActive) {
      setBoms([]);
      setBomId("");
      return;
    }
    void loadBoms(produtoId);
  }, [produtoId, isActive, role]); // eslint-disable-line react-hooks/exhaustive-deps

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
    const hasValidOperacao = operacoes.some((op) => op.centro_trabalho_id !== "");
    if (!hasValidOperacao) {
      return "Adicione ao menos uma operacao com centro de trabalho.";
    }
    return null;
  }

  function buildOperacoesPayload(): OrcamentoOperacaoInput[] {
    return operacoes
      .filter((op) => op.centro_trabalho_id !== "")
      .map((op) => ({
        centro_trabalho_id: Number(op.centro_trabalho_id),
        setup_min: op.setup_min || "0",
        ciclo_min: op.ciclo_min || "0",
        descricao: op.descricao.trim() || undefined,
      }));
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

  return (
    <main className="mx-auto grid max-w-7xl gap-4 px-4 py-4 lg:grid-cols-[1.2fr_1fr]">
      <section className="space-y-4">
        <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
          <h2 className="mb-3 text-lg font-semibold">Gerador de Orcamentos</h2>
          {loadingCatalogos && <p className="text-sm text-slate-400">Carregando cadastros...</p>}

          <form className="grid gap-3" onSubmit={handleSimular}>
            <div className="grid gap-3 md:grid-cols-2">
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
                <span className="text-slate-400">Produto final</span>
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
                <span className="text-slate-400">Quantidade</span>
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

            <label className="grid gap-1 text-sm">
              <span className="text-slate-400">Observacao</span>
              <textarea
                className="min-h-20 rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                value={observacao}
                onChange={(event) => setObservacao(event.target.value)}
                placeholder="Informacoes tecnicas adicionais do projeto..."
              />
            </label>

            <div className="rounded-lg border border-slate-800 bg-slate-950 p-3">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold">Operacoes de usinagem/montagem</h3>
                <button
                  type="button"
                  className="rounded border border-slate-700 px-2 py-1 text-xs hover:bg-slate-800"
                  onClick={addOperacao}
                >
                  + Adicionar operacao
                </button>
              </div>
              <div className="space-y-2">
                {operacoes.map((op, index) => (
                  <div key={`op-${index}`} className="grid gap-2 rounded border border-slate-800 p-2 md:grid-cols-12">
                    <label className="grid gap-1 text-xs md:col-span-4">
                      <span className="text-slate-400">Centro</span>
                      <select
                        className="rounded-md border border-slate-700 bg-slate-900 px-2 py-2"
                        value={op.centro_trabalho_id}
                        onChange={(event) => updateOperacao(index, "centro_trabalho_id", event.target.value)}
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
                        onChange={(event) => updateOperacao(index, "setup_min", event.target.value)}
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
                        onChange={(event) => updateOperacao(index, "ciclo_min", event.target.value)}
                      />
                    </label>
                    <label className="grid gap-1 text-xs md:col-span-3">
                      <span className="text-slate-400">Descricao</span>
                      <input
                        className="rounded-md border border-slate-700 bg-slate-900 px-2 py-2"
                        value={op.descricao}
                        onChange={(event) => updateOperacao(index, "descricao", event.target.value)}
                        placeholder="Ex.: Corte CNC"
                      />
                    </label>
                    <div className="grid content-end md:col-span-1">
                      <button
                        type="button"
                        className="rounded border border-rose-700 px-2 py-2 text-xs text-rose-200 hover:bg-rose-900/30 disabled:opacity-40"
                        onClick={() => removeOperacao(index)}
                        disabled={operacoes.length === 1}
                      >
                        Remover
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="submit"
                className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium hover:bg-sky-500 disabled:opacity-50"
                disabled={submitting}
              >
                Simular custo
              </button>
              <button
                type="button"
                className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
                disabled={submitting}
                onClick={() => void handleCriarOrcamento()}
              >
                Salvar orcamento
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
      </section>
    </main>
  );
}
