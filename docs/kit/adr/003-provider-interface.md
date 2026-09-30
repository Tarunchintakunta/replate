# ADR 003 — One editor interface, three providers

Date: 2026-09-30. Status: accepted.

## Decision

All image edits go through `ImageEditor`. The default provider is `mock`. `gemini` is the first live provider. `wavespeed` with model `wavespeed-ai/flux-kontext-pro` is the quality provider. Fal and Replicate are not dependencies in v1.

## Why

Mock makes CI free and deterministic. Gemini is the live key the builder can create from the account they already use. WaveSpeed’s Kontext Pro is the same class of model this category sells, at about $0.04 a run, and it is good at type. Adding Fal and Replicate now is three SDKs for one job.

## Consequence

A fourth provider is a new issue, a new file, and a test double. It is not a rewrite of the route.
