# v0-listings: Archive Summary

**Status:** Archived
**Original window:** 2026-02-22 to 2026-03-02
**Superseded by:** `docs/architecture.md`

---

## Why this work existed

The v0-listings docs explored how to reliably ingest businesses-for-sale listings and avoid low-fidelity query matches (for example: returning unrelated listings for an HVAC thesis).

---

## Durable findings

1. Marketplace ingestion must be treated as a pipeline, not an ad-hoc live query.
2. Query fidelity requires post-fetch normalization and filtering against the user thesis.
3. A local canonical store is required for fast repeatable queries and benchmarking.
4. Source quirks are significant: BizBuySell behavior, URL/category structure, pagination, and anti-bot constraints require dedicated source logic.
5. Source payload persistence is useful for replay/debug and schema drift handling.

---

## Technical intent captured by this archive

1. Normalize source records to one shared listing model before downstream use.
2. Persist canonical listing records with idempotent upserts.
3. Keep source-specific extraction isolated from downstream logic.
4. Validate listing relevance explicitly to reduce false positives.

---

## Cleanup note

The detailed planning/research/discovery files in `docs/feature/v0-listings/` were consolidated into this summary to reduce duplication and keep one active architecture narrative.
