import type { ApiError, DocumentState, Health, InpaintMode } from "./types";

async function parse<T>(response: Response): Promise<T> {
  const text = await response.text();
  const data = text ? (JSON.parse(text) as T & { error?: ApiError }) : ({} as T & { error?: ApiError });
  if (!response.ok) {
    const error = data.error ?? {
      code: "INTERNAL",
      message: response.statusText || "The request failed.",
    };
    throw error;
  }
  return data;
}

export async function getHealth(): Promise<Health> {
  const response = await fetch("/api/health");
  return parse<Health>(response);
}

export async function uploadFile(file: File): Promise<DocumentState> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/upload", { method: "POST", body });
  return parse<DocumentState>(response);
}

export async function detectText(documentId: string): Promise<DocumentState> {
  const response = await fetch(`/api/document/${documentId}/detect-text`, { method: "POST" });
  const data = await parse<{ document: DocumentState }>(response);
  return data.document;
}

export async function replaceText(
  documentId: string,
  regionId: string,
  newText: string,
  mode: InpaintMode,
): Promise<{
  document: DocumentState;
  mode_used: string;
  draw_source?: string;
  fallback_reason: string | null;
}> {
  const response = await fetch(`/api/document/${documentId}/replace-text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ region_id: regionId, new_text: newText, mode }),
  });
  return parse(response);
}

export async function undo(documentId: string): Promise<DocumentState> {
  const response = await fetch(`/api/document/${documentId}/undo`, { method: "POST" });
  return parse<DocumentState>(response);
}

export async function redo(documentId: string): Promise<DocumentState> {
  const response = await fetch(`/api/document/${documentId}/redo`, { method: "POST" });
  return parse<DocumentState>(response);
}

export async function resetDocument(documentId: string): Promise<DocumentState> {
  const response = await fetch(`/api/document/${documentId}/reset`, { method: "POST" });
  return parse<DocumentState>(response);
}

export async function exportDocument(
  documentId: string,
  format: "png" | "jpg" | "pdf",
): Promise<{ filename: string; blob: Blob }> {
  const response = await fetch(`/api/document/${documentId}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format }),
  });
  const data = await parse<{ filename: string; download_url: string }>(response);
  const file = await fetch(data.download_url);
  if (!file.ok) {
    throw { code: "EXPORT_FAILED", message: "The export could not be downloaded." } satisfies ApiError;
  }
  return { filename: data.filename, blob: await file.blob() };
}

export function pageImageUrl(
  documentId: string,
  page: number,
  variant: "current" | "original",
  version: number,
): string {
  return `/api/document/${documentId}/pages/${page}/image?variant=${variant}&v=${version}`;
}

export function thumbnailUrl(documentId: string, page: number, version: number): string {
  return `/api/document/${documentId}/pages/${page}/thumbnail?v=${version}`;
}
