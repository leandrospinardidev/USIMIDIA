import type { CentroTrabalhoCadastro, TipoMaquina } from "../types";

export interface CncMachinePreset {
  id: string;
  nome: string;
  descricao: string;
  tipo_maquina: TipoMaquina;
  rpm_max: number;
  fator_tempo: number;
  setup_base_min: number;
  margem_lucro_pct: number;
  custo_indireto_pct: number;
  rpm_hints: string[];
}

export interface CncMaterialPreset {
  id: string;
  nome: string;
  liga_ref: string;
  vc_referencia_m_min: string;
  fz_referencia_mm_dente: string;
  fator_tempo: number;
  margem_lucro_pct: number;
  notas: string;
}

export interface CncOperationPreset {
  id: string;
  nome: string;
  descricao: string;
  base_cycle_min: number;
  fator_operacao: number;
  setup_adicional_min: number;
  custo_indireto_pct: number;
  margem_lucro_pct: number;
}

export type CncPieceType = "EIXO" | "FLANGE" | "BLOCO";

export interface CncAutoStrategyInput {
  machinePreset: CncMachinePreset;
  materialPreset: CncMaterialPreset;
  pieceType: CncPieceType;
  diametroMm?: number | null;
  comprimentoMm?: number | null;
}

export interface CncAutoStrategyOperation {
  operationPresetId: CncOperationPreset["id"];
  operationNome: string;
  descricao: string;
  cicloMin: string;
  setupMin: string;
}

export interface CncAutoStrategyResult {
  pieceType: CncPieceType;
  dimensionFactor: number;
  furosEstimados: number;
  suggestedMarginPct: number;
  suggestedIndirectPct: number;
  operations: CncAutoStrategyOperation[];
}

export const CNC_MACHINE_PRESETS: readonly CncMachinePreset[] = [
  {
    id: "vmc_8k_bt40",
    nome: "Centro vertical 8k RPM (BT40)",
    descricao: "Linha de entrada, boa robustez para aco e aluminio.",
    tipo_maquina: "FRESA_CNC",
    rpm_max: 8000,
    fator_tempo: 1.15,
    setup_base_min: 18,
    margem_lucro_pct: 26,
    custo_indireto_pct: 8,
    rpm_hints: ["8k", "8000", "bt40"],
  },
  {
    id: "vmc_12k_bt40",
    nome: "Centro vertical 12k RPM (BT40)",
    descricao: "Perfil mais comum no mercado para usinagem geral.",
    tipo_maquina: "FRESA_CNC",
    rpm_max: 12000,
    fator_tempo: 1,
    setup_base_min: 15,
    margem_lucro_pct: 24,
    custo_indireto_pct: 7,
    rpm_hints: ["12k", "12000", "bt40"],
  },
  {
    id: "vmc_15k_hsk",
    nome: "Centro de alta rotacao 15k RPM (HSK)",
    descricao: "Alta produtividade para aluminio e acabamento fino.",
    tipo_maquina: "FRESA_CNC",
    rpm_max: 15000,
    fator_tempo: 0.85,
    setup_base_min: 12,
    margem_lucro_pct: 22,
    custo_indireto_pct: 6,
    rpm_hints: ["15k", "15000", "hsk", "high speed"],
  },
];

export const CNC_MATERIAL_PRESETS: readonly CncMaterialPreset[] = [
  {
    id: "al_6061",
    nome: "Aluminio usinavel",
    liga_ref: "AA 6061 / 6082",
    vc_referencia_m_min: "220-360",
    fz_referencia_mm_dente: "0.06-0.14",
    fator_tempo: 0.82,
    margem_lucro_pct: 22,
    notas: "Alta usinabilidade, boa remocao em desbaste.",
  },
  {
    id: "aco_1045",
    nome: "Aco carbono medio",
    liga_ref: "SAE 1045",
    vc_referencia_m_min: "120-210",
    fz_referencia_mm_dente: "0.05-0.11",
    fator_tempo: 1.08,
    margem_lucro_pct: 28,
    notas: "Padrao industrial para eixos e componentes mecanicos.",
  },
  {
    id: "inox_304",
    nome: "Aco inox austenitico",
    liga_ref: "AISI 304/316",
    vc_referencia_m_min: "70-140",
    fz_referencia_mm_dente: "0.03-0.08",
    fator_tempo: 1.28,
    margem_lucro_pct: 34,
    notas: "Exige refrigeracao e estrategia de corte conservadora.",
  },
];

export const CNC_OPERATION_PRESETS: readonly CncOperationPreset[] = [
  {
    id: "desbaste",
    nome: "Desbaste",
    descricao: "Remocao de volume principal da peca.",
    base_cycle_min: 10,
    fator_operacao: 1.15,
    setup_adicional_min: 4,
    custo_indireto_pct: 7,
    margem_lucro_pct: 26,
  },
  {
    id: "acabamento",
    nome: "Acabamento",
    descricao: "Passes finos para tolerancia e rugosidade.",
    base_cycle_min: 8,
    fator_operacao: 1.02,
    setup_adicional_min: 3,
    custo_indireto_pct: 6,
    margem_lucro_pct: 24,
  },
  {
    id: "furacao",
    nome: "Furacao",
    descricao: "Furos passantes/cegos em ciclo dedicado.",
    base_cycle_min: 6,
    fator_operacao: 0.95,
    setup_adicional_min: 2,
    custo_indireto_pct: 6,
    margem_lucro_pct: 23,
  },
  {
    id: "rosqueamento",
    nome: "Rosqueamento",
    descricao: "Operacao de rosca interna/externa.",
    base_cycle_min: 5,
    fator_operacao: 0.9,
    setup_adicional_min: 2,
    custo_indireto_pct: 6,
    margem_lucro_pct: 24,
  },
];

const AUTO_STRATEGY_OPERATION_IDS: readonly CncOperationPreset["id"][] = [
  "desbaste",
  "acabamento",
  "furacao",
];

function findOperationPreset(id: CncOperationPreset["id"]): CncOperationPreset {
  const found = CNC_OPERATION_PRESETS.find((item) => item.id === id);
  if (!found) {
    throw new Error(`Preset de operacao nao encontrado: ${id}`);
  }
  return found;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function toPositiveNumber(value: number | null | undefined, fallback: number): number {
  if (!Number.isFinite(value) || value === null || value === undefined || value <= 0) {
    return fallback;
  }
  return Number(value);
}

function getPieceFactor(pieceType: CncPieceType): number {
  switch (pieceType) {
    case "EIXO":
      return 1.04;
    case "FLANGE":
      return 0.98;
    case "BLOCO":
      return 1.12;
    default:
      return 1;
  }
}

function calculateDimensionFactor(
  pieceType: CncPieceType,
  diametroMm?: number | null,
  comprimentoMm?: number | null
): number {
  const d = toPositiveNumber(diametroMm, 60);
  const l = toPositiveNumber(comprimentoMm, 120);

  if (pieceType === "EIXO") {
    return clamp(0.7 + d / 300 + l / 700, 0.7, 2.2);
  }
  if (pieceType === "FLANGE") {
    return clamp(0.75 + d / 260 + l / 400, 0.7, 2.1);
  }
  return clamp(0.8 + d / 220 + l / 350, 0.75, 2.4);
}

function estimateHoles(pieceType: CncPieceType, diametroMm?: number | null): number {
  const d = toPositiveNumber(diametroMm, 60);
  if (pieceType === "FLANGE") {
    return clamp(Math.round(d / 22), 4, 16);
  }
  if (pieceType === "BLOCO") {
    return clamp(Math.round(d / 35), 2, 10);
  }
  return clamp(Math.round(d / 55), 1, 6);
}

export function buildAutoStrategyPlan(input: CncAutoStrategyInput): CncAutoStrategyResult {
  const operations = AUTO_STRATEGY_OPERATION_IDS.map(findOperationPreset);
  const pieceFactor = getPieceFactor(input.pieceType);
  const dimensionFactor = calculateDimensionFactor(
    input.pieceType,
    input.diametroMm,
    input.comprimentoMm
  );
  const furosEstimados = estimateHoles(input.pieceType, input.diametroMm);
  const setupPieceExtra = input.pieceType === "EIXO" ? 2 : input.pieceType === "BLOCO" ? 4 : 3;

  const computedOperations = operations.map((operation) => {
    const furacaoFactor = operation.id === "furacao" ? 1 + (furosEstimados - 1) * 0.08 : 1;
    const cycle =
      operation.base_cycle_min *
      input.machinePreset.fator_tempo *
      input.materialPreset.fator_tempo *
      operation.fator_operacao *
      pieceFactor *
      dimensionFactor *
      furacaoFactor;
    const setup = Math.max(
      input.machinePreset.setup_base_min,
      input.machinePreset.setup_base_min * 0.65 + setupPieceExtra + operation.setup_adicional_min
    );
    return {
      operationPresetId: operation.id,
      operationNome: operation.nome,
      descricao: `${operation.nome} automatico (${input.pieceType.toLowerCase()})`,
      cicloMin: Math.max(0.4, cycle).toFixed(2),
      setupMin: Math.max(1, setup).toFixed(2),
    } satisfies CncAutoStrategyOperation;
  });

  return {
    pieceType: input.pieceType,
    dimensionFactor,
    furosEstimados,
    suggestedMarginPct: Math.max(
      input.machinePreset.margem_lucro_pct,
      input.materialPreset.margem_lucro_pct,
      24
    ),
    suggestedIndirectPct: Math.max(input.machinePreset.custo_indireto_pct, 6),
    operations: computedOperations,
  };
}

function normalize(value: string): string {
  return value.trim().toLowerCase();
}

export function suggestCentroForMachinePreset(
  centros: readonly CentroTrabalhoCadastro[],
  machinePreset: CncMachinePreset
): CentroTrabalhoCadastro | null {
  if (centros.length === 0) {
    return null;
  }

  const byType = centros.filter((centro) => centro.tipo_maquina === machinePreset.tipo_maquina);
  const candidates = byType.length > 0 ? byType : centros;

  const hinted = candidates.find((centro) => {
    const text = normalize(`${centro.codigo} ${centro.nome}`);
    return machinePreset.rpm_hints.some((hint) => text.includes(normalize(hint)));
  });
  return hinted ?? candidates[0] ?? null;
}

export function calculateCycleMinFromPreset(
  machinePreset: CncMachinePreset,
  materialPreset: CncMaterialPreset,
  operationPreset: CncOperationPreset
): string {
  const cycle =
    operationPreset.base_cycle_min *
    machinePreset.fator_tempo *
    materialPreset.fator_tempo *
    operationPreset.fator_operacao;
  return Math.max(0.5, cycle).toFixed(2);
}

export function calculateSetupMinFromPreset(
  machinePreset: CncMachinePreset,
  operationPreset: CncOperationPreset,
  centro?: CentroTrabalhoCadastro | null
): string {
  const setup = Math.max(
    machinePreset.setup_base_min,
    Number(centro?.setup_padrao_min ?? 0) + operationPreset.setup_adicional_min
  );
  return Math.max(1, setup).toFixed(2);
}

