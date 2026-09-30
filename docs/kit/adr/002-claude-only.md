# ADR 002 — Claude is the only implementer

Date: 2026-09-30. Status: accepted.

## Decision

Claude Code writes every commit in the Replate repo. Gemini and Grok do not edit the tree, open pull requests, or receive secrets.

## Why

Split authorship across chat models produces two styles, broken handoffs, and keys pasted into the wrong window. One writer can follow the issue order and the test gate.

A chat subscription is not a build agent. Claude’s GitHub connection is the one that files issues and opens pull requests.

## Consequence

`GEMINI.md` tells Gemini to refuse implementation. If a snippet from another model is useful, Claude rewrites it in a normal commit and the pull request says so.
