import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  createEventoMes,
  createRefugoMes,
  getIndicadoresKpis,
  getOrdem,
  getRastreabilidadeOrdem,
  getResumoTempoMes,
  listEventosMes,
  listIndicadoresOrdens,
  listOrdens,
  listRefugosMes,
} from "./api";
import type {
  Apontamento,
  EventoMES,
  IndicadorOrdemItem,
  KpisGerais,
  OrdemDetail,
  OrdemListItem,
  OrdemOperacao,
  PageMeta,
  Refugo,
  RastreabilidadeOrdem,
  ResumoTempo,
  UserRole,
} from "./types";

type ViewMode = "mes" | "indicadores";

const USER_ROLES: UserRole[] = ["operador", "pcp", "admin", "compras"];
const STATUS_FILTERS = [
  "",
  "ABERTA",
  "PLANEJADA",
  "EM_PRODUCAO",
  "PAUSADA",
  "FINALIZADA",
  "CANCELADA",
];

function formatNumber(value: string | number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) {
    return "-";
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return String(value);
  }
  return parsed.toLocaleString("pt-BR", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("pt-BR");
}

function statusBadge(status: string): string {
  switch (status) {
    case "FINALIZADA":
    case "CONCLUIDA":
      return "bg-emerald-500/20 text-emerald-300 border-emerald-400/30";
    case "EM_PRODUCAO":
    case "EM_EXECUCAO":
      return "bg-sky-500/20 text-sky-300 border-sky-400/30";
    case "PAUSADA":
      return "bg-amber-500/20 text-amber-300 border-amber-400/30";
    case "CANCELADA":
      return "bg-rose-500/20 text-rose-300 border-rose-400/30";
    case "PLANEJADA":
    case "PENDENTE":
      return "bg-violet-500/20 text-violet-300 border-violet-400/30";
    default:
      return "bg-slate-500/20 text-slate-300 border-slate-400/30";
  }
}

export default function App() {
  const [viewMode, setViewMode] = useState<ViewMode>("mes");
  const [role, setRole] = useState<UserRole>("operador");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // MES
  const [mesSearchInput, setMesSearchInput] = useState("");
  const [mesSearchApplied, setMesSearchApplied] = useState("");
  const [mesStatusFilter, setMesStatusFilter] = useState("");
  const [mesPage, setMesPage] = useState(1);
  const [mesMeta, setMesMeta] = useState<PageMeta>({ page: 1, page_size: 10, total: 0 });
  const [ordens, setOrdens] = useState<OrdemListItem[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null);
  const [ordemDetail, setOrdemDetail] = useState<OrdemDetail | null>(null);
  const [selectedOperationId, setSelectedOperationId] = useState<number | null>(null);
  const [eventos, setEventos] = useState<Apontamento[]>([]);
  const [refugos, setRefugos] = useState<Refugo[]>([]);
  const [resumo, setResumo] = useState<ResumoTempo | null>(null);
  const [dataHoraEvento, setDataHoraEvento] = useState("");
  const [motivoEvento, setMotivoEvento] = useState("");
  const [quantidadeProduzida, setQuantidadeProduzida] = useState("0");
  const [quantidadeRefugo, setQuantidadeRefugo] = useState("1");
  const [motivoRefugo, setMotivoRefugo] = useState("");
  const [loadingOrdens, setLoadingOrdens] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingMes, setLoadingMes] = useState(false);
  const [submittingMes, setSubmittingMes] = useState(false);

  // Indicadores
  const [indicSearchInput, setIndicSearchInput] = useState("");
  const [indicSearchApplied, setIndicSearchApplied] = useState("");
  const [indicStatusFilter, setIndicStatusFilter] = useState("");
  const [indicPeriodoInicio, setIndicPeriodoInicio] = useState("");
  const [indicPeriodoFim, setIndicPeriodoFim] = useState("");
  const [indicPage, setIndicPage] = useState(1);
  const [indicMeta, setIndicMeta] = useState<PageMeta>({ page: 1, page_size: 10, total: 0 });
  const [indicadores, setIndicadores] = useState<IndicadorOrdemItem[]>([]);
  const [kpis, setKpis] = useState<KpisGerais | null>(null);
  const [loadingIndicadores, setLoadingIndicadores] = useState(false);
  const [loadingRastreabilidade, setLoadingRastreabilidade] = useState(false);
  const [rastreabilidade, setRastreabilidade] = useState<RastreabilidadeOrdem | null>(null);

  const selectedOperation = useMemo<OrdemOperacao | null>(() => {
    if (!ordemDetail || !selectedOperationId) {
      return null;
    }
    return ordemDetail.operacoes.find((op) => op.id === selectedOperationId) ?? null;
  }, [ordemDetail, selectedOperationId]);

  const mesTotalPages = Math.max(1, Math.ceil(mesMeta.total / Math.max(1, mesMeta.page_size)));
  const indicTotalPages = Math.max(1, Math.ceil(indicMeta.total / Math.max(1, indicMeta.page_size)));

  useEffect(() => {
    if (viewMode !== "mes") {
      return;
    }
    void loadMesOrdens();
  }, [viewMode, role, mesPage, mesSearchApplied, mesStatusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (viewMode !== "indicadores") {
      return;
    }
    void loadIndicadores();
  }, [viewMode, role, indicPage, indicSearchApplied, indicStatusFilter, indicPeriodoInicio, indicPeriodoFim]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (viewMode !== "mes" || !selectedOperationId) {
      setEventos([]);
      setRefugos([]);
      setResumo(null);
      return;
    }
    void loadMesData(selectedOperationId);
  }, [viewMode, selectedOperationId, role]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadMesOrdens(): Promise<void> {
    setLoadingOrdens(true);
    setError(null);
    try {
      const response = await listOrdens(role, {
        page: mesPage,
        pageSize: 10,
        search: mesSearchApplied || undefined,
        status: mesStatusFilter || undefined,
      });
      setOrdens(response.items);
      setMesMeta(response.meta);
      if (selectedOrderId) {
        const stillExists = response.items.some((item) => item.id === selectedOrderId);
        if (!stillExists) {
          setSelectedOrderId(null);
          setOrdemDetail(null);
          setSelectedOperationId(null);
        }
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingOrdens(false);
    }
  }

  async function loadMesOrderDetail(ordemId: number): Promise<void> {
    setLoadingDetail(true);
    setError(null);
    try {
      const detail = await getOrdem(role, ordemId);
      setOrdemDetail(detail);
      if (detail.operacoes.length > 0) {
        setSelectedOperationId((prev) => {
          if (prev && detail.operacoes.some((op) => op.id === prev)) {
            return prev;
          }
          return detail.operacoes[0].id;
        });
      } else {
        setSelectedOperationId(null);
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingDetail(false);
    }
  }

  async function loadMesData(ordemOperacaoId: number): Promise<void> {
    setLoadingMes(true);
    setError(null);
    try {
      const [eventosResp, refugosResp, resumoResp] = await Promise.all([
        listEventosMes(role, ordemOperacaoId),
        listRefugosMes(role, ordemOperacaoId),
        getResumoTempoMes(role, ordemOperacaoId),
      ]);
      setEventos(eventosResp.items);
      setRefugos(refugosResp.items);
      setResumo(resumoResp);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingMes(false);
    }
  }

  async function handleSelectOrder(ordemId: number): Promise<void> {
    setSelectedOrderId(ordemId);
    await loadMesOrderDetail(ordemId);
  }

  async function handleQuickEvent(evento: EventoMES): Promise<void> {
    if (!selectedOperationId || !selectedOrderId) {
      return;
    }
    setSubmittingMes(true);
    setError(null);
    setSuccess(null);
    try {
      const payload: {
        evento: EventoMES;
        data_hora_evento?: string;
        motivo?: string;
        quantidade_produzida?: string;
      } = { evento };

      if (dataHoraEvento.trim()) {
        payload.data_hora_evento = new Date(dataHoraEvento).toISOString();
      }
      if (motivoEvento.trim()) {
        payload.motivo = motivoEvento.trim();
      }
      if (evento === "STOP" && Number(quantidadeProduzida) > 0) {
        payload.quantidade_produzida = quantidadeProduzida;
      }

      await createEventoMes(role, selectedOperationId, payload);
      setSuccess(`Evento ${evento} registrado com sucesso.`);
      await loadMesOrderDetail(selectedOrderId);
      await loadMesData(selectedOperationId);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmittingMes(false);
    }
  }

  async function handleSubmitRefugo(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedOperationId || !selectedOrderId) {
      return;
    }
    setSubmittingMes(true);
    setError(null);
    setSuccess(null);
    try {
      await createRefugoMes(role, selectedOperationId, {
        quantidade: quantidadeRefugo,
        motivo: motivoRefugo,
      });
      setQuantidadeRefugo("1");
      setMotivoRefugo("");
      setSuccess("Refugo registrado com sucesso.");
      await loadMesOrderDetail(selectedOrderId);
      await loadMesData(selectedOperationId);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmittingMes(false);
    }
  }

  async function loadIndicadores(): Promise<void> {
    setLoadingIndicadores(true);
    setError(null);
    try {
      const [kpisResp, indicadoresResp] = await Promise.all([
        getIndicadoresKpis(role, {
          periodoInicio: indicPeriodoInicio || undefined,
          periodoFim: indicPeriodoFim || undefined,
          status: indicStatusFilter || undefined,
        }),
        listIndicadoresOrdens(role, {
          page: indicPage,
          pageSize: 10,
          search: indicSearchApplied || undefined,
          status: indicStatusFilter || undefined,
          periodoInicio: indicPeriodoInicio || undefined,
          periodoFim: indicPeriodoFim || undefined,
        }),
      ]);
      setKpis(kpisResp);
      setIndicadores(indicadoresResp.items);
      setIndicMeta(indicadoresResp.meta);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingIndicadores(false);
    }
  }

  async function handleOpenRastreabilidade(ordemId: number): Promise<void> {
    setLoadingRastreabilidade(true);
    setError(null);
    setSuccess(null);
    try {
      const data = await getRastreabilidadeOrdem(role, ordemId);
      setRastreabilidade(data);
      setSuccess(`Rastreabilidade da OP ${data.numero_op} carregada.`);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoadingRastreabilidade(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/90">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold text-slate-100">ERP Industrial Web</h1>
              <p className="mt-1 text-sm text-slate-400">
                Painel operacional com OP/MES e dashboard de indicadores.
              </p>
            </div>
            <label className="grid gap-1 text-sm">
              <span className="text-slate-400">Perfil (X-User-Role)</span>
              <select
                className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
                value={role}
                onChange={(event) => {
                  setRole(event.target.value as UserRole);
                  setError(null);
                  setSuccess(null);
                }}
              >
                {USER_ROLES.map((userRole) => (
                  <option key={userRole} value={userRole}>
                    {userRole}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="flex gap-2">
            <button
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                viewMode === "mes"
                  ? "bg-sky-600 text-white"
                  : "border border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800"
              }`}
              onClick={() => setViewMode("mes")}
            >
              Operacao MES
            </button>
            <button
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                viewMode === "indicadores"
                  ? "bg-sky-600 text-white"
                  : "border border-slate-700 bg-slate-950 text-slate-200 hover:bg-slate-800"
              }`}
              onClick={() => setViewMode("indicadores")}
            >
              Dashboard Indicadores
            </button>
          </div>
        </div>
      </header>

      {viewMode === "mes" ? (
        <main className="mx-auto grid max-w-7xl gap-4 px-4 py-4 lg:grid-cols-[380px_1fr]">
          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="mb-4 grid gap-3">
              <label className="grid gap-1 text-sm">
                <span className="text-slate-400">Pesquisar OP</span>
                <div className="flex gap-2">
                  <input
                    className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
                    value={mesSearchInput}
                    onChange={(event) => setMesSearchInput(event.target.value)}
                    placeholder="Numero OP ou produto"
                  />
                  <button
                    className="rounded-md bg-sky-600 px-3 py-2 text-sm font-medium hover:bg-sky-500"
                    onClick={() => {
                      setMesPage(1);
                      setMesSearchApplied(mesSearchInput.trim());
                    }}
                  >
                    Buscar
                  </button>
                </div>
              </label>

              <label className="grid gap-1 text-sm">
                <span className="text-slate-400">Status</span>
                <select
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
                  value={mesStatusFilter}
                  onChange={(event) => {
                    setMesStatusFilter(event.target.value);
                    setMesPage(1);
                  }}
                >
                  {STATUS_FILTERS.map((status) => (
                    <option key={status || "todos"} value={status}>
                      {status || "TODOS"}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mb-3 flex items-center justify-between text-xs text-slate-400">
              <span>
                Total: {mesMeta.total} | Pag. {mesPage}/{mesTotalPages}
              </span>
              <div className="flex gap-2">
                <button
                  className="rounded border border-slate-700 px-2 py-1 hover:bg-slate-800 disabled:opacity-50"
                  onClick={() => setMesPage((prev) => Math.max(1, prev - 1))}
                  disabled={mesPage <= 1}
                >
                  Anterior
                </button>
                <button
                  className="rounded border border-slate-700 px-2 py-1 hover:bg-slate-800 disabled:opacity-50"
                  onClick={() => setMesPage((prev) => Math.min(mesTotalPages, prev + 1))}
                  disabled={mesPage >= mesTotalPages}
                >
                  Proxima
                </button>
                <button
                  className="rounded border border-slate-700 px-2 py-1 hover:bg-slate-800"
                  onClick={() => void loadMesOrdens()}
                >
                  Atualizar
                </button>
              </div>
            </div>

            <div className="max-h-[64vh] space-y-2 overflow-auto pr-1">
              {loadingOrdens && <p className="text-sm text-slate-400">Carregando ordens...</p>}
              {!loadingOrdens && ordens.length === 0 && (
                <p className="text-sm text-slate-400">Nenhuma ordem encontrada.</p>
              )}
              {ordens.map((ordem) => (
                <button
                  key={ordem.id}
                  className={`w-full rounded-lg border px-3 py-3 text-left transition ${
                    selectedOrderId === ordem.id
                      ? "border-sky-500 bg-sky-500/10"
                      : "border-slate-800 bg-slate-950 hover:border-slate-600"
                  }`}
                  onClick={() => void handleSelectOrder(ordem.id)}
                >
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="font-medium">{ordem.numero_op}</span>
                    <span className={`rounded border px-2 py-0.5 text-xs ${statusBadge(ordem.status)}`}>
                      {ordem.status}
                    </span>
                  </div>
                  <p className="text-sm text-slate-300">{ordem.produto_codigo}</p>
                  <p className="line-clamp-2 text-xs text-slate-400">{ordem.produto_descricao}</p>
                  <p className="mt-2 text-xs text-slate-400">
                    Planejada: {formatNumber(ordem.quantidade_planejada, 3)} | Produzida:{" "}
                    {formatNumber(ordem.quantidade_produzida, 3)}
                  </p>
                </button>
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            {!selectedOrderId && (
              <p className="text-sm text-slate-400">
                Selecione uma ordem na coluna ao lado para abrir o painel de operacao MES.
              </p>
            )}

            {selectedOrderId && loadingDetail && (
              <p className="text-sm text-slate-400">Carregando detalhe da OP...</p>
            )}

            {ordemDetail && (
              <div className="space-y-4">
                <header className="rounded-lg border border-slate-800 bg-slate-950 p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-lg font-semibold">
                      {ordemDetail.numero_op} - {ordemDetail.produto_codigo}
                    </h2>
                    <span className={`rounded border px-2 py-1 text-xs ${statusBadge(ordemDetail.status)}`}>
                      {ordemDetail.status}
                    </span>
                  </div>
                  <p className="text-sm text-slate-300">{ordemDetail.produto_descricao}</p>
                  <p className="text-xs text-slate-400">
                    Planejada: {formatNumber(ordemDetail.quantidade_planejada, 3)} | Produzida:{" "}
                    {formatNumber(ordemDetail.quantidade_produzida, 3)} | Refugada:{" "}
                    {formatNumber(ordemDetail.quantidade_refugada, 3)}
                  </p>
                </header>

                {ordemDetail.operacoes.length === 0 ? (
                  <p className="text-sm text-slate-400">Esta ordem nao possui operacoes planejadas.</p>
                ) : (
                  <label className="grid gap-1 text-sm">
                    <span className="text-slate-400">Operacao</span>
                    <select
                      className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2"
                      value={selectedOperationId ?? ""}
                      onChange={(event) => setSelectedOperationId(Number(event.target.value))}
                    >
                      {ordemDetail.operacoes.map((op) => (
                        <option key={op.id} value={op.id}>
                          Seq {op.sequencia} - {op.centro_codigo} - {op.status}
                        </option>
                      ))}
                    </select>
                  </label>
                )}

                {selectedOperation && (
                  <div className="grid gap-4 xl:grid-cols-2">
                    <div className="space-y-3 rounded-lg border border-slate-800 bg-slate-950 p-3">
                      <h3 className="text-sm font-semibold text-slate-200">Controle MES</h3>
                      <p className="text-xs text-slate-400">
                        Operacao {selectedOperation.sequencia} - {selectedOperation.centro_nome}
                      </p>

                      <div className="grid gap-2 sm:grid-cols-2">
                        <button
                          className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
                          onClick={() => void handleQuickEvent("START")}
                          disabled={submittingMes}
                        >
                          START
                        </button>
                        <button
                          className="rounded-md bg-amber-600 px-3 py-2 text-sm font-medium hover:bg-amber-500 disabled:opacity-50"
                          onClick={() => void handleQuickEvent("PAUSA")}
                          disabled={submittingMes}
                        >
                          PAUSA
                        </button>
                        <button
                          className="rounded-md bg-sky-600 px-3 py-2 text-sm font-medium hover:bg-sky-500 disabled:opacity-50"
                          onClick={() => void handleQuickEvent("RETOMADA")}
                          disabled={submittingMes}
                        >
                          RETOMADA
                        </button>
                        <button
                          className="rounded-md bg-rose-600 px-3 py-2 text-sm font-medium hover:bg-rose-500 disabled:opacity-50"
                          onClick={() => void handleQuickEvent("STOP")}
                          disabled={submittingMes}
                        >
                          STOP
                        </button>
                      </div>

                      <div className="grid gap-2">
                        <label className="grid gap-1 text-xs">
                          <span className="text-slate-400">Data/hora do evento (opcional)</span>
                          <input
                            type="datetime-local"
                            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
                            value={dataHoraEvento}
                            onChange={(event) => setDataHoraEvento(event.target.value)}
                          />
                        </label>
                        <label className="grid gap-1 text-xs">
                          <span className="text-slate-400">Quantidade produzida para STOP</span>
                          <input
                            type="number"
                            min="0"
                            step="0.001"
                            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
                            value={quantidadeProduzida}
                            onChange={(event) => setQuantidadeProduzida(event.target.value)}
                          />
                        </label>
                        <label className="grid gap-1 text-xs">
                          <span className="text-slate-400">Motivo (opcional)</span>
                          <input
                            className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2"
                            value={motivoEvento}
                            onChange={(event) => setMotivoEvento(event.target.value)}
                            placeholder="Troca de ferramenta, setup, etc."
                          />
                        </label>
                      </div>

                      <form className="grid gap-2 border-t border-slate-800 pt-3" onSubmit={handleSubmitRefugo}>
                        <p className="text-xs font-semibold text-slate-300">Registrar refugo</p>
                        <input
                          type="number"
                          min="0.001"
                          step="0.001"
                          required
                          className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs"
                          value={quantidadeRefugo}
                          onChange={(event) => setQuantidadeRefugo(event.target.value)}
                          placeholder="Quantidade"
                        />
                        <input
                          required
                          className="rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs"
                          value={motivoRefugo}
                          onChange={(event) => setMotivoRefugo(event.target.value)}
                          placeholder="Motivo do refugo"
                        />
                        <button
                          type="submit"
                          className="rounded-md bg-violet-600 px-3 py-2 text-sm font-medium hover:bg-violet-500 disabled:opacity-50"
                          disabled={submittingMes}
                        >
                          Salvar refugo
                        </button>
                      </form>
                    </div>

                    <div className="space-y-3 rounded-lg border border-slate-800 bg-slate-950 p-3">
                      <h3 className="text-sm font-semibold text-slate-200">Resumo em tempo real</h3>
                      {loadingMes && <p className="text-xs text-slate-400">Carregando resumo MES...</p>}
                      {resumo && (
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <Metric label="Status operacao" value={resumo.status_operacao} />
                          <Metric label="Status OP" value={resumo.status_ordem} />
                          <Metric label="Horas reais" value={formatNumber(resumo.total_horas, 3)} />
                          <Metric label="Eventos" value={String(resumo.quantidade_eventos)} />
                          <Metric
                            label="Produzido total"
                            value={formatNumber(resumo.quantidade_produzida_total, 3)}
                          />
                          <Metric
                            label="Refugo total"
                            value={formatNumber(resumo.quantidade_refugada_total, 3)}
                          />
                        </div>
                      )}

                      <div className="grid gap-2 pt-2">
                        <h4 className="text-xs font-semibold text-slate-300">Ultimos eventos</h4>
                        <div className="max-h-36 space-y-1 overflow-auto pr-1">
                          {eventos.length === 0 && (
                            <p className="text-xs text-slate-500">Sem eventos registrados.</p>
                          )}
                          {eventos.map((item) => (
                            <div
                              key={item.id}
                              className="rounded border border-slate-800 bg-slate-900 px-2 py-1 text-xs"
                            >
                              <div className="flex items-center justify-between">
                                <span className={`rounded border px-1 ${statusBadge(item.status_operacao)}`}>
                                  {item.evento}
                                </span>
                                <span className="text-slate-400">{formatDateTime(item.data_hora_evento)}</span>
                              </div>
                              <p className="text-slate-400">
                                Produzido: {formatNumber(item.quantidade_produzida, 3)}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="grid gap-2 pt-2">
                        <h4 className="text-xs font-semibold text-slate-300">Refugos</h4>
                        <div className="max-h-28 space-y-1 overflow-auto pr-1">
                          {refugos.length === 0 && <p className="text-xs text-slate-500">Sem refugos.</p>}
                          {refugos.map((item) => (
                            <div
                              key={item.id}
                              className="rounded border border-slate-800 bg-slate-900 px-2 py-1 text-xs"
                            >
                              <p className="text-slate-200">
                                {formatNumber(item.quantidade, 3)} - {item.motivo}
                              </p>
                              <p className="text-slate-400">{formatDateTime(item.data_hora)}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>
        </main>
      ) : (
        <main className="mx-auto max-w-7xl space-y-4 px-4 py-4">
          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <h2 className="mb-3 text-lg font-semibold">Dashboard de Indicadores</h2>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <label className="grid gap-1 text-sm">
                <span className="text-slate-400">Pesquisar OP/produto</span>
                <input
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
                  value={indicSearchInput}
                  onChange={(event) => setIndicSearchInput(event.target.value)}
                  placeholder="OP, codigo ou descricao"
                />
              </label>

              <label className="grid gap-1 text-sm">
                <span className="text-slate-400">Status</span>
                <select
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
                  value={indicStatusFilter}
                  onChange={(event) => {
                    setIndicStatusFilter(event.target.value);
                    setIndicPage(1);
                  }}
                >
                  {STATUS_FILTERS.map((status) => (
                    <option key={status || "todos"} value={status}>
                      {status || "TODOS"}
                    </option>
                  ))}
                </select>
              </label>

              <label className="grid gap-1 text-sm">
                <span className="text-slate-400">Periodo inicio</span>
                <input
                  type="date"
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
                  value={indicPeriodoInicio}
                  onChange={(event) => {
                    setIndicPeriodoInicio(event.target.value);
                    setIndicPage(1);
                  }}
                />
              </label>

              <label className="grid gap-1 text-sm">
                <span className="text-slate-400">Periodo fim</span>
                <input
                  type="date"
                  className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100"
                  value={indicPeriodoFim}
                  onChange={(event) => {
                    setIndicPeriodoFim(event.target.value);
                    setIndicPage(1);
                  }}
                />
              </label>

              <div className="grid content-end gap-2">
                <button
                  className="rounded-md bg-sky-600 px-3 py-2 text-sm font-medium hover:bg-sky-500"
                  onClick={() => {
                    setIndicPage(1);
                    setIndicSearchApplied(indicSearchInput.trim());
                  }}
                >
                  Buscar
                </button>
                <button
                  className="rounded-md border border-slate-700 px-3 py-2 text-sm hover:bg-slate-800"
                  onClick={() => void loadIndicadores()}
                >
                  Atualizar
                </button>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-300">KPIs agregados</h3>
            {loadingIndicadores && <p className="text-sm text-slate-400">Carregando indicadores...</p>}
            {kpis && (
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <Metric label="Total ordens" value={String(kpis.total_ordens)} />
                <Metric label="Qtd planejada" value={formatNumber(kpis.quantidade_planejada_total, 3)} />
                <Metric label="Qtd produzida" value={formatNumber(kpis.quantidade_produzida_total, 3)} />
                <Metric label="Qtd refugada" value={formatNumber(kpis.quantidade_refugada_total, 3)} />
                <Metric label="Refugo %" value={`${formatNumber(kpis.refugo_pct, 2)}%`} />
                <Metric label="Tempo planejado (h)" value={formatNumber(kpis.tempo_planejado_horas, 3)} />
                <Metric label="Tempo real (h)" value={formatNumber(kpis.tempo_real_horas, 3)} />
                <Metric label="Eficiencia %" value={`${formatNumber(kpis.eficiencia_pct, 2)}%`} />
                <Metric
                  label="Custo planejado total"
                  value={`R$ ${formatNumber(kpis.custo_total_planejado, 2)}`}
                />
                <Metric label="Custo real total" value={`R$ ${formatNumber(kpis.custo_total_real, 2)}`} />
                <Metric
                  label="Custo total orcado"
                  value={kpis.custo_total_orcado ? `R$ ${formatNumber(kpis.custo_total_orcado, 2)}` : "-"}
                />
                <Metric
                  label="Desvio real x orcado"
                  value={
                    kpis.desvio_custo_real_vs_orcado
                      ? `R$ ${formatNumber(kpis.desvio_custo_real_vs_orcado, 2)}`
                      : "-"
                  }
                />
              </div>
            )}
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div className="mb-3 flex items-center justify-between text-sm">
              <h3 className="font-semibold text-slate-300">Indicadores por OP</h3>
              <span className="text-slate-400">
                Pag. {indicPage}/{indicTotalPages} | Total: {indicMeta.total}
              </span>
            </div>

            <div className="overflow-auto">
              <table className="min-w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-700 text-left text-xs uppercase text-slate-400">
                    <th className="px-2 py-2">OP</th>
                    <th className="px-2 py-2">Status</th>
                    <th className="px-2 py-2">Produto</th>
                    <th className="px-2 py-2">Refugo %</th>
                    <th className="px-2 py-2">Eficiencia %</th>
                    <th className="px-2 py-2">Custo real</th>
                    <th className="px-2 py-2">Acao</th>
                  </tr>
                </thead>
                <tbody>
                  {!loadingIndicadores && indicadores.length === 0 && (
                    <tr>
                      <td className="px-2 py-3 text-slate-500" colSpan={7}>
                        Nenhum indicador encontrado.
                      </td>
                    </tr>
                  )}
                  {indicadores.map((item) => (
                    <tr key={item.ordem_id} className="border-b border-slate-800 text-slate-200">
                      <td className="px-2 py-2">
                        <div className="font-medium">{item.numero_op}</div>
                        <div className="text-xs text-slate-400">{item.data_emissao}</div>
                      </td>
                      <td className="px-2 py-2">
                        <span className={`rounded border px-2 py-0.5 text-xs ${statusBadge(item.status)}`}>
                          {item.status}
                        </span>
                      </td>
                      <td className="px-2 py-2">
                        <div className="font-medium">{item.produto_codigo}</div>
                        <div className="line-clamp-2 text-xs text-slate-400">{item.produto_descricao}</div>
                      </td>
                      <td className="px-2 py-2">{formatNumber(item.refugo_pct, 2)}%</td>
                      <td className="px-2 py-2">{formatNumber(item.eficiencia_pct, 2)}%</td>
                      <td className="px-2 py-2">R$ {formatNumber(item.custo_total_real, 2)}</td>
                      <td className="px-2 py-2">
                        <button
                          className="rounded border border-sky-700 px-2 py-1 text-xs text-sky-200 hover:bg-sky-900/40"
                          onClick={() => void handleOpenRastreabilidade(item.ordem_id)}
                        >
                          Rastrear
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-3 flex gap-2 text-sm">
              <button
                className="rounded border border-slate-700 px-3 py-1 hover:bg-slate-800 disabled:opacity-50"
                onClick={() => setIndicPage((prev) => Math.max(1, prev - 1))}
                disabled={indicPage <= 1}
              >
                Anterior
              </button>
              <button
                className="rounded border border-slate-700 px-3 py-1 hover:bg-slate-800 disabled:opacity-50"
                onClick={() => setIndicPage((prev) => Math.min(indicTotalPages, prev + 1))}
                disabled={indicPage >= indicTotalPages}
              >
                Proxima
              </button>
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-300">Rastreabilidade da OP</h3>
            {loadingRastreabilidade && <p className="text-sm text-slate-400">Carregando rastreabilidade...</p>}
            {!loadingRastreabilidade && !rastreabilidade && (
              <p className="text-sm text-slate-500">Clique em "Rastrear" na tabela para abrir os detalhes.</p>
            )}
            {rastreabilidade && (
              <div className="space-y-3">
                <div className="rounded border border-slate-800 bg-slate-950 p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <h4 className="font-semibold">
                      {rastreabilidade.numero_op} - {rastreabilidade.produto_codigo}
                    </h4>
                    <span className={`rounded border px-2 py-1 text-xs ${statusBadge(rastreabilidade.status)}`}>
                      {rastreabilidade.status}
                    </span>
                  </div>
                  <p className="text-sm text-slate-300">{rastreabilidade.produto_descricao}</p>
                  <p className="text-xs text-slate-400">
                    Planejada: {formatNumber(rastreabilidade.quantidade_planejada, 3)} | Produzida:{" "}
                    {formatNumber(rastreabilidade.quantidade_produzida, 3)} | Refugada:{" "}
                    {formatNumber(rastreabilidade.quantidade_refugada, 3)}
                  </p>
                </div>

                <div className="grid gap-3 lg:grid-cols-2">
                  <div className="rounded border border-slate-800 bg-slate-950 p-3">
                    <h5 className="mb-2 text-xs font-semibold uppercase text-slate-400">Operacoes</h5>
                    <div className="max-h-48 space-y-1 overflow-auto pr-1">
                      {rastreabilidade.operacoes.map((op) => (
                        <div key={op.ordem_operacao_id} className="rounded border border-slate-800 px-2 py-2 text-xs">
                          <div className="flex items-center justify-between">
                            <span>
                              Seq {op.sequencia} - {op.centro_codigo}
                            </span>
                            <span className={`rounded border px-1 ${statusBadge(op.status)}`}>{op.status}</span>
                          </div>
                          <p className="text-slate-400">
                            Tempo real: {formatNumber(op.tempo_real_horas, 3)}h | Eventos: {op.quantidade_eventos} |
                            Refugos: {op.quantidade_refugos}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded border border-slate-800 bg-slate-950 p-3">
                    <h5 className="mb-2 text-xs font-semibold uppercase text-slate-400">Fluxo de retalhos</h5>
                    <div className="max-h-48 space-y-1 overflow-auto pr-1">
                      {rastreabilidade.fluxo_retalhos.length === 0 && (
                        <p className="text-xs text-slate-500">Sem retalhos vinculados.</p>
                      )}
                      {rastreabilidade.fluxo_retalhos.map((fluxo, index) => (
                        <div key={`${fluxo.lote_origem_id}-${fluxo.lote_retalho_id}-${index}`} className="text-xs">
                          Lote origem #{fluxo.lote_origem_id} ➜ Retalho #{fluxo.lote_retalho_id}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="rounded border border-slate-800 bg-slate-950 p-3">
                  <h5 className="mb-2 text-xs font-semibold uppercase text-slate-400">Movimentacoes de estoque</h5>
                  <div className="max-h-64 overflow-auto">
                    <table className="min-w-full text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 text-left text-slate-400">
                          <th className="px-2 py-1">Data/Hora</th>
                          <th className="px-2 py-1">Tipo</th>
                          <th className="px-2 py-1">Lote</th>
                          <th className="px-2 py-1">Insumo</th>
                          <th className="px-2 py-1">Qtd</th>
                          <th className="px-2 py-1">Custo aprox.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rastreabilidade.movimentacoes.map((mov) => (
                          <tr key={mov.id} className="border-b border-slate-900">
                            <td className="px-2 py-1 text-slate-300">{formatDateTime(mov.data_hora)}</td>
                            <td className="px-2 py-1">{mov.tipo_movimento}</td>
                            <td className="px-2 py-1">
                              {mov.codigo_lote}
                              {mov.is_retalho ? " (retalho)" : ""}
                            </td>
                            <td className="px-2 py-1">{mov.insumo_codigo}</td>
                            <td className="px-2 py-1">{formatNumber(mov.quantidade, 3)}</td>
                            <td className="px-2 py-1">R$ {formatNumber(mov.custo_aproximado, 2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </section>
        </main>
      )}

      {(error || success) && (
        <div className="fixed bottom-4 right-4 w-full max-w-sm space-y-2 px-4 lg:px-0">
          {error && (
            <div className="rounded-lg border border-rose-500/40 bg-rose-500/20 px-3 py-2 text-sm text-rose-100">
              {error}
            </div>
          )}
          {success && (
            <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/20 px-3 py-2 text-sm text-emerald-100">
              {success}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900 px-2 py-1">
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className="font-medium text-slate-200">{value}</p>
    </div>
  );
}

function extractErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.detail} (HTTP ${error.status})`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Erro inesperado.";
}
