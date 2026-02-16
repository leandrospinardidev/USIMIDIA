import { useEffect, useState } from "react";

import { getIndicadoresKpis, getRastreabilidadeOrdem, listIndicadoresOrdens } from "../api";
import type {
  IndicadorOrdemItem,
  KpisGerais,
  PageMeta,
  RastreabilidadeOrdem,
  UserRole,
} from "../types";
import { extractErrorMessage } from "../utils/errors";
import { formatDateTime, formatNumber, statusBadge } from "../utils/ui";
import { Metric } from "./Metric";

interface IndicadoresPanelProps {
  role: UserRole;
  statusFilters: readonly string[];
  isActive: boolean;
  onError: (message: string | null) => void;
  onSuccess: (message: string | null) => void;
}

export function IndicadoresPanel({
  role,
  statusFilters,
  isActive,
  onError,
  onSuccess,
}: IndicadoresPanelProps) {
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

  const indicTotalPages = Math.max(1, Math.ceil(indicMeta.total / Math.max(1, indicMeta.page_size)));

  useEffect(() => {
    if (!isActive) {
      return;
    }
    void loadIndicadores();
  }, [isActive, role, indicPage, indicSearchApplied, indicStatusFilter, indicPeriodoInicio, indicPeriodoFim]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadIndicadores(): Promise<void> {
    setLoadingIndicadores(true);
    onError(null);
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
      onError(extractErrorMessage(err));
    } finally {
      setLoadingIndicadores(false);
    }
  }

  async function handleOpenRastreabilidade(ordemId: number): Promise<void> {
    setLoadingRastreabilidade(true);
    onError(null);
    onSuccess(null);
    try {
      const data = await getRastreabilidadeOrdem(role, ordemId);
      setRastreabilidade(data);
      onSuccess(`Rastreabilidade da OP ${data.numero_op} carregada.`);
    } catch (err) {
      onError(extractErrorMessage(err));
    } finally {
      setLoadingRastreabilidade(false);
    }
  }

  return (
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
              {statusFilters.map((status) => (
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
            <Metric label="Custo planejado total" value={`R$ ${formatNumber(kpis.custo_total_planejado, 2)}`} />
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
                      Lote origem #{fluxo.lote_origem_id} -> Retalho #{fluxo.lote_retalho_id}
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
  );
}
