import { useEffect, useMemo, useState } from "react";
import {
  detectText,
  exportDocument,
  getHealth,
  pageImageUrl,
  redo,
  replaceText,
  resetDocument,
  thumbnailUrl,
  undo,
  uploadFile,
} from "./api";
import type { ApiError, DocumentState, Health, TextRegion } from "./types";


export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [healthDown, setHealthDown] = useState(false);
  const [documentState, setDocumentState] = useState<DocumentState | null>(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [compare, setCompare] = useState(0);

  useEffect(() => {
    getHealth()
      .then((value) => {
        setHealth(value);
        setHealthDown(false);
      })
      .catch(() => setHealthDown(true));
  }, []);

  const page = documentState?.pages[pageIndex];
  const pageRegions = useMemo(
    () => (documentState ? documentState.regions.filter((region) => region.page === pageIndex) : []),
    [documentState, pageIndex],
  );
  const selected = pageRegions.find((region) => region.id === selectedId) ?? null;

  function fail(caught: unknown) {
    const apiError = caught as ApiError;
    setError({
      code: apiError.code || "INTERNAL",
      message: apiError.message || "Something went wrong.",
    });
  }

  async function onUpload(file: File) {
    setBusy("Uploading…");
    setError(null);
    setNotice(null);
    setCompare(0);
    setSelectedId(null);
    setDraft("");
    try {
      const uploaded = await uploadFile(file);
      setDocumentState(uploaded);
      setPageIndex(0);
      setBusy(
        uploaded.page_count > 1
          ? `Reading text on ${uploaded.page_count} pages. The first run loads the OCR model and can take a minute.`
          : "Reading text. The first run loads the OCR model and can take a minute.",
      );
      setDetecting(true);
      const detected = await detectText(uploaded.id);
      setDocumentState(detected);
      setNotice(
        detected.regions.length === 1
          ? "1 text region found. Click it, type the replacement, then apply."
          : `${detected.regions.length} text regions found. Click one, type the replacement, then apply.`,
      );
    } catch (caught) {
      fail(caught);
    } finally {
      setDetecting(false);
      setBusy(null);
    }
  }

  function selectRegion(region: TextRegion) {
    setSelectedId(region.id);
    setPageIndex(region.page);
    setDraft((current) => (selectedId === region.id ? current : region.text));
    setError(null);
  }

  async function onApply() {
    if (!documentState || !selected || !draft.trim()) return;
    if (draft.trim() === selected.text) {
      setNotice("That line already says this. Edit the text, then apply.");
      return;
    }
    setBusy("Replacing text…");
    setError(null);
    try {
      const result = await replaceText(documentState.id, selected.id, draft.trim(), "auto");
      setDocumentState(result.document);
      setDraft(draft.trim());
      setNotice("Text replaced.");
      setCompare(0);
    } catch (caught) {
      fail(caught);
    } finally {
      setBusy(null);
    }
  }

  async function runHistory(action: "undo" | "redo" | "reset") {
    if (!documentState) return;
    setBusy(action === "reset" ? "Resetting…" : action === "undo" ? "Undoing…" : "Redoing…");
    setError(null);
    try {
      const next =
        action === "undo"
          ? await undo(documentState.id)
          : action === "redo"
            ? await redo(documentState.id)
            : await resetDocument(documentState.id);
      setDocumentState(next);
      setNotice(action === "reset" ? "All edits were cleared." : action === "undo" ? "Undid the last edit." : "Redid the edit.");
      setCompare(0);
    } catch (caught) {
      fail(caught);
    } finally {
      setBusy(null);
    }
  }

  async function onExport(format: "png" | "jpg" | "pdf") {
    if (!documentState) return;
    setBusy("Exporting…");
    setError(null);
    try {
      const { filename, blob } = await exportDocument(documentState.id, format);
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement("a");
      link.href = url;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(url);
      setNotice(`Downloaded ${filename}.`);
    } catch (caught) {
      fail(caught);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <p className="brand">Local ReWords</p>
          <p className="tagline">Replace text in images and PDFs.</p>
        </div>
        {(healthDown || (health && (!health.inpaint_ai.ready || (health.text_edit?.enabled && !health.text_edit.key)))) && (
          <p className="health">
            {healthDown ? "Backend not reachable" : "Setup incomplete: some edits may look approximate"}
          </p>
        )}
      </header>

      {error && (
        <div className="banner error" role="alert">
          <span>{error.message}</span>
          <button type="button" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}
      {notice && !error && <div className="banner notice">{notice}</div>}

      {!documentState ? (
        <Uploader disabled={Boolean(busy)} onFile={onUpload} />
      ) : (
        <main className="workspace">
          <section className="stage-column">
            {documentState.page_count > 1 && (
              <div className="thumbs" aria-label="Pages">
                {documentState.pages.map((item) => (
                  <button
                    key={item.index}
                    type="button"
                    data-testid={`page-thumb-${item.index}`}
                    className={item.index === pageIndex ? "thumb active" : "thumb"}
                    onClick={() => {
                      setPageIndex(item.index);
                      setSelectedId(null);
                      setDraft("");
                    }}
                  >
                    <img
                      src={thumbnailUrl(documentState.id, item.index, item.version)}
                      alt={`Page ${item.index + 1}`}
                    />
                    <span>
                      {item.index + 1}
                      {item.version > 0 ? " · edited" : ""} · {item.kind}
                    </span>
                  </button>
                ))}
              </div>
            )}
            {page && (
              <Viewer
                documentId={documentState.id}
                detecting={detecting}
                page={page}
                regions={pageRegions}
                selectedId={selectedId}
                compare={compare}
                onSelect={selectRegion}
              />
            )}
            <div className="compare-row">
              <label htmlFor="compare">Before / after</label>
              <input
                id="compare"
                type="range"
                min={0}
                max={100}
                value={compare}
                onChange={(event) => setCompare(Number(event.target.value))}
                disabled={!documentState.edits.length}
              />
              <span>{documentState.edits.length ? (compare === 0 ? "Edited" : compare === 100 ? "Original" : "Comparing") : "Apply a change to compare"}</span>
            </div>
          </section>
          <TextPanel
            regions={pageRegions}
            selected={selected}
            draft={draft}
            fileKind={documentState.file_kind}
            canUndo={documentState.can_undo}
            canRedo={documentState.can_redo}
            busy={busy}
            detecting={detecting}
            warnings={documentState.warnings}
            edits={documentState.edits}
            onDraft={setDraft}
            onSelect={selectRegion}
            onApply={onApply}
            onCancel={() => {
              setDraft("");
              setSelectedId(null);
            }}
            onUndo={() => runHistory("undo")}
            onRedo={() => runHistory("redo")}
            onReset={() => {
              if (window.confirm("Discard every edit and go back to the original file?")) {
                void runHistory("reset");
              }
            }}
            onExport={onExport}
            onNew={() => {
              setDocumentState(null);
              setSelectedId(null);
              setDraft("");
              setNotice(null);
              setError(null);
            }}
          />
        </main>
      )}
      {busy && !detecting && (
        <div className="busy" role="status">
          {busy}
        </div>
      )}
    </div>
  );
}

function Uploader({ disabled, onFile }: { disabled: boolean; onFile: (file: File) => void }) {
  return (
    <section
      className="drop"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        const file = event.dataTransfer.files[0];
        if (file) onFile(file);
      }}
    >
      <h1>Drop a PNG, JPG, or PDF</h1>
      <p>
        Text is detected locally. Click a highlighted line, type what should replace it, and export the result.
        The original upload is kept untouched.
      </p>
      <label className="file-button">
        Choose a file
        <input
          data-testid="file-input"
          type="file"
          accept=".png,.jpg,.jpeg,.pdf,image/png,image/jpeg,application/pdf"
          disabled={disabled}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onFile(file);
            event.target.value = "";
          }}
        />
      </label>
      <ul>
        <li>Images stay images. Text PDFs stay text where the page has real text.</li>
        <li>Scanned pages are rebuilt visually. Mixed PDFs are handled page by page.</li>
        <li>Up to 25 MB and 30 pages.</li>
      </ul>
    </section>
  );
}

function PageImage({ src, alt, className, style }: { src: string; alt: string; className?: string; style?: React.CSSProperties }) {
  const [state, setState] = useState<{ src: string; tries: number; loaded: boolean }>({ src, tries: 0, loaded: false });
  if (state.src !== src && !state.src.startsWith(`${src}&retry=`)) setState({ src, tries: 0, loaded: false });
  const shown = state.tries ? `${src}&retry=${state.tries}` : src;
  return (
    <>
      {!state.loaded && !className && <div className="page-placeholder" aria-hidden="true" />}
      <img
        src={shown}
        alt={alt}
        className={className}
        style={state.loaded ? style : { ...style, position: className ? undefined : "absolute", opacity: 0 }}
        onLoad={() => setState((current) => ({ ...current, loaded: true }))}
        onError={() => {
          // Large pages can fail while the backend is busy reading text. Retry a few times.
          if (state.tries < 4) window.setTimeout(() => setState((current) => ({ ...current, tries: current.tries + 1 })), 800 * (state.tries + 1));
        }}
      />
    </>
  );
}

function Viewer({
  documentId,
  detecting,
  page,
  regions,
  selectedId,
  compare,
  onSelect,
}: {
  documentId: string;
  detecting: boolean;
  page: DocumentState["pages"][number];
  regions: TextRegion[];
  selectedId: string | null;
  compare: number;
  onSelect: (region: TextRegion) => void;
}) {
  const current = pageImageUrl(documentId, page.index, "current", page.version);
  const original = pageImageUrl(documentId, page.index, "original", 0);
  return (
    <div className="frame" data-testid="viewer">
      <div className="sheet">
        <PageImage src={current} alt="Current page" />
        {compare > 0 && (
          <PageImage
            src={original}
            alt="Original page"
            className="original-layer"
            style={{ clipPath: `inset(0 ${100 - compare}% 0 0)` }}
          />
        )}
        {detecting && (
          <div className="scanning" role="status" aria-live="polite">
            <div className="scan-line" />
            <span className="scan-label">Reading text…</span>
          </div>
        )}
        <svg className="overlay" viewBox={`0 0 ${page.width_px} ${page.height_px}`} preserveAspectRatio="none">
          {regions.map((region) => (
            <polygon
              key={region.id}
              data-testid={`region-shape-${region.id}`}
              points={region.polygon.map((point) => point.join(",")).join(" ")}
              className={region.id === selectedId ? "region selected" : "region"}
              onClick={() => onSelect(region)}
            />
          ))}
        </svg>
      </div>
    </div>
  );
}

function TextPanel({
  regions,
  selected,
  draft,
  fileKind,
  canUndo,
  canRedo,
  busy,
  detecting,
  warnings,
  edits,
  onDraft,
  onSelect,
  onApply,
  onCancel,
  onUndo,
  onRedo,
  onReset,
  onExport,
  onNew,
}: {
  regions: TextRegion[];
  selected: TextRegion | null;
  draft: string;
  fileKind: "image" | "pdf";
  canUndo: boolean;
  canRedo: boolean;
  busy: string | null;
  detecting: boolean;
  warnings: string[];
  edits: DocumentState["edits"];
  onDraft: (value: string) => void;
  onSelect: (region: TextRegion) => void;
  onApply: () => void;
  onCancel: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onReset: () => void;
  onExport: (format: "png" | "jpg" | "pdf") => void;
  onNew: () => void;
}) {
  return (
    <aside className="panel">
      <div className="panel-actions">
        <button type="button" onClick={onUndo} disabled={!canUndo || Boolean(busy)}>
          Undo
        </button>
        <button type="button" onClick={onRedo} disabled={!canRedo || Boolean(busy)}>
          Redo
        </button>
        <button type="button" onClick={onReset} disabled={!canUndo || Boolean(busy)}>
          Reset
        </button>
        <button type="button" className="ghost" onClick={onNew} disabled={Boolean(busy)}>
          New file
        </button>
      </div>
      <h2>Detected text</h2>
      {detecting ? (
        <>
          <p className="hint">Reading text…</p>
          <ul className="region-list" aria-hidden="true">
            {[72, 55, 84, 40, 63].map((width, index) => (
              <li key={index} className="skeleton-row">
                <span className="skeleton" style={{ width: `${width}%` }} />
                <span className="skeleton small" style={{ width: `${width / 2}%` }} />
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="hint">{regions.length ? `${regions.length} on this page` : "Nothing detected on this page."}</p>
      )}
      <ul className="region-list">
        {regions.map((region) => (
          <li key={region.id}>
              <button
              type="button"
              data-testid={`region-${region.id}`}
              className={selected?.id === region.id ? "region-button selected" : "region-button"}
              onClick={() => onSelect(region)}
            >
              <span className="swatch" style={{ background: rgb(region.style.color_rgb) }} />
              <span>
                <strong>{region.text}</strong>
              </span>
            </button>
          </li>
        ))}
      </ul>
      <div className="editor">
        {selected ? (
          <>
            <p className="original-text">Selected: {selected.text}</p>
            <label htmlFor="replacement">Replacement</label>
            <input
              id="replacement"
              data-testid="replacement"
              value={draft}
              placeholder="Type the new text"
              onChange={(event) => onDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") onApply();
              }}
            />
            <div className="panel-actions">
              <button
                type="button"
                className="primary"
                data-testid="apply"
                onClick={onApply}
                disabled={!draft.trim() || Boolean(busy)}
              >
                Apply change
              </button>
              <button type="button" onClick={onCancel}>
                Cancel
              </button>
            </div>
          </>
        ) : (
          <p className="hint">Select a highlighted region on the page, or a line in the list.</p>
        )}
      </div>
      <div className="panel-actions export-row">
        {fileKind === "image" ? (
          <>
            <button type="button" data-testid="export-png" onClick={() => onExport("png")} disabled={Boolean(busy)}>
              Export PNG
            </button>
            <button type="button" data-testid="export-jpg" onClick={() => onExport("jpg")} disabled={Boolean(busy)}>
              Export JPG
            </button>
          </>
        ) : (
          <button type="button" data-testid="export-pdf" onClick={() => onExport("pdf")} disabled={Boolean(busy)}>
            Export PDF
          </button>
        )}
      </div>
      {warnings.length > 0 && (
        <ul className="warnings">
          {warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
      {edits.length > 0 && (
        <ol className="edits">
          {edits.map((edit, index) => (
            <li key={`${edit.region_id}-${index}`}>
              Page {edit.page + 1}: “{edit.before}” → “{edit.after}”
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}

function rgb(channels: number[]): string {
  const [red, green, blue] = channels;
  return `rgb(${red ?? 0}, ${green ?? 0}, ${blue ?? 0})`;
}
