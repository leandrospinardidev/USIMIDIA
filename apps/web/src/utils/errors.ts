import { ApiError } from "../api";

export function extractErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.detail} (HTTP ${error.status})`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Erro inesperado.";
}
