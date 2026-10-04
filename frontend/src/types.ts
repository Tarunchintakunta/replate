export type Align = "left" | "center" | "right";
export type InpaintMode = "auto" | "fast" | "ai";

export type TextRegion = {
  id: string;
  page: number;
  text: string;
  bbox: { x: number; y: number; width: number; height: number };
  polygon: number[][];
  confidence: number;
  rotation: number;
  source: "ocr" | "pdf_text";
  style: {
    family: "sans" | "serif" | "mono" | "condensed" | "receipt";
    bold: boolean;
    font_label?: string;
    font_confidence?: number | null;
    font_size_px: number;
    color_rgb: number[];
    align: Align;
    source_font_name?: string | null;
  };
};

export type PageInfo = {
  index: number;
  kind: "image" | "native" | "scanned";
  width_px: number;
  height_px: number;
  version: number;
};

export type EditRecord = {
  region_id: string;
  page: number;
  before: string;
  after: string;
  mode_requested: string;
  mode_used: string;
  draw_source?: "glyphs" | "synthesized" | "ai_text" | "font" | "pdf_text";
  match_score?: number | null;
  fallback_reason: string | null;
};

export type DocumentState = {
  id: string;
  original_filename: string;
  media_type: "png" | "jpeg" | "pdf";
  file_kind: "image" | "pdf";
  page_count: number;
  pages: PageInfo[];
  regions: TextRegion[];
  detected: boolean;
  edits: EditRecord[];
  page_glyphs?: Record<string, string>;
  warnings: string[];
  can_undo: boolean;
  can_redo: boolean;
};

export type ApiError = {
  code: string;
  message: string;
  detail?: unknown;
};

export type Health = {
  status: string;
  device: { torch: string; paddle: string };
  inpaint_ai: { ready: boolean; detail: string; loaded: boolean };
  ocr: { loaded: boolean; lang: string };
  text_edit?: { engine: string; key: boolean; enabled: boolean };
};
