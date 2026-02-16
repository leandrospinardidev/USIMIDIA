import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  createEventoMes,
  createRefugoMes,
  getOrdem,
  getResumoTempoMes,
  listEventosMes,
  listOrdens,
  listRefugosMes,
} from "../api";
import type {
  Apontamento,
  EventoMES,
  OrdemDetail,
  OrdemListItem,
  OrdemOperacao,
  PageMeta,
  Refugo,
  ResumoTempo,
  UserRole,
} from "../types";
import { extractErrorMessage } from "../utils/errors";
import { formatDateTime, formatNumber, statusBadge } from "../utils/ui";
import { Metric } from "./Metric";

interface MesPanelProps {
  role: UserRole;
  statusFilters: readonly string[];
  isActive: boolean;
  onError: (message: string | null) => void;
  onSuccess: (message: string | null) => void;
}

export function MesPanel({ role, statusFilters, isActive, onError, onSuccess }: MesPanelProps) {
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

  const selectedOperation = useMemo<OrdemOperacao | null>(() => {
    if (!ordemDetail || !selectedOperationId) {
      return null;
    }
    return ordemDetail.operacoes.find((op) => op.id === selectedOperationId) ?? null;
  }, [ordemDetail, selectedOperationId]);

  const mesTotalPages = Math.max(1, Math.ceil(mesMeta.total / Math.max(1, mesMeta.page_size)));

  useEffect(() => {
    if (!isActive) {
      return;
    }
    void loadMesOrdens();
  }, [isActive, role, mesPage, mesSearchApplied, mesStatusFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isActive || !selectedOperationId) {
      setEventos([]);
      setRefugos([]);
      setResumo(null);
      return;
    }
    void loadMesData(selectedOperationId);
  }, [isActive, role, selectedOperationId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadMesOrdens(): Promise<void> {
    setLoadingOrdens(true);
    onError(null);
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
      onError(extractErrorMessage(err));
    } finally {
      setLoadingOrdens(false);
    }
  }

  async function loadMesOrderDetail(ordemId: number): Promise<void> {
    setLoadingDetail(true);
    onError(null);
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
      onError(extractErrorMessage(err));
    } finally {
      setLoadingDetail(false);
    }
  }

  async function loadMesData(ordemOperacaoId: number): Promise<void> {
    setLoadingMes(true);
    onError(null);
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
      onError(extractErrorMessage(err));
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
    onError(null);
    onSuccess(null);
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
      onSuccess(`Evento ${evento} registrado com sucesso.`);
      await loadMesOrderDetail(selectedOrderId);
      await loadMesData(selectedOperationId);
    } catch (err) {
      onError(extractErrorMessage(err));
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
    onError(null);
    onSuccess(null);
    try {
      await createRefugoMes(role, selectedOperationId, {
        quantidade: quantidadeRefugo,
        motivo: motivoRefugo,
      });
      setQuantidadeRefugo("1");
      setMotivoRefugo("");
      onSuccess("Refugo registrado com sucesso.");
      await loadMesOrderDetail(selectedOrderId);
      await loadMesData(selectedOperationId);
    } catch (err) {
      onError(extractErrorMessage(err));
    } finally {
      setSubmittingMes(false);
    }
  }

  return (
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
              {statusFilters.map((status) => (
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
                      <Metric label="Produzido total" value={formatNumber(resumo.quantidade_produzida_total, 3)} />
                      <Metric label="Refugo total" value={formatNumber(resumo.quantidade_refugada_total, 3)} />
                    </div>
                  )}

                  <div className="grid gap-2 pt-2">
                    <h4 className="text-xs font-semibold text-slate-300">Ultimos eventos</h4>
                    <div className="max-h-36 space-y-1 overflow-auto pr-1">
                      {eventos.length === 0 && <p className="text-xs text-slate-500">Sem eventos registrados.</p>}
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
  );
}
