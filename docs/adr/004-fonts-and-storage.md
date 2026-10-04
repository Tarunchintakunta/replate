# ADR 004 — Bundled fonts and local files

Status: accepted

Fonts: Liberation Sans, Serif, and Mono, plus Barlow Condensed and Share Tech Mono. All are SIL OFL (`fonts/LICENSE` and `fonts/OFL-*.txt`). On a photo or scan, characters that stay in the string are copied from the original line. New characters are cut from elsewhere on the page and repainted with that line's ink and blur. A bundled face is used only for letters the page does not contain, and only when that face overlaps the ink by at least 45% at its natural width. PDF text still uses the embedded face's family flags.

Storage: `StorageProvider` is implemented by per-document directories under `storage/`. No database. An object-storage implementation can replace `LocalStorage` later without changing the edit pipeline.
