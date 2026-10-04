# ADR 005 — Vite, React, TypeScript

Status: accepted

The UI is a Vite app that talks to FastAPI under `/api`. The dev server proxies that prefix, so the browser only needs one origin. There is no component-library requirement in the product spec; the controls are small and specific to this editor (page stage, region list, mode switch). Adding a general component kit would not remove the custom stage.
