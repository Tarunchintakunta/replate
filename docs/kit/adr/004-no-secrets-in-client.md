# ADR 004 — Secrets stay on the server

Date: 2026-09-30. Status: accepted.

## Decision

Environment variables are read in server modules only. The client bundle must not embed a config object of provider keys, model defaults that include vendor URLs with tokens, or database settings. `NEXT_PUBLIC_` is limited to the app name if needed. Health checks return booleans.

## Why

A competitor in this category shipped their default model IDs, storage vendor, and payment integrations inside a public JavaScript file because a server config object was imported by client code. The values of the secrets were empty. The architecture was not.

## Consequence

ESLint or a unit test scans `next build` output and fails if it finds `API_KEY`, `SECRET`, `sk_live`, `sk_test`, `whsec_`, or `BEGIN PRIVATE KEY`.
