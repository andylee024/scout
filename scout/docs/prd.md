# Scout Product Scope

**Product:** Scout  
**Positioning:** SMB sourcing data pipeline  
**Status:** Active scope  
**Last Updated:** 2026-03-21

## Purpose

Scout exists to turn a plain-English market query into database-ready records for partner review and owner outreach.

## Current Product

1. `scout run` parses a natural-language query into `industry` and `location`.
2. The pipeline fetches operating businesses from Google Maps.
3. The pipeline fetches businesses-for-sale listings from BizBuySell.
4. Raw payloads and canonical records are persisted to local storage.
5. The result is a repeatable dataset that can later be enriched and synced into a database.

The TUI remains in the repo, but it is not the canonical product surface.

## Near-Term Product Target

```text
google_maps      -> businesses ----\
bizbuysell       -> listings ------ +--> merge --> leads + owner_contacts
clodo            -> owners --------/
google_reviews   -> review signals /

reddit sentiment -> supplemental context
```

The primary shared review surface is expected to be Supabase.

## Goals

1. Make market reruns deterministic and repeatable.
2. Preserve raw source payloads for replay and debugging.
3. Normalize source data into canonical records before database sync.
4. Merge businesses, listings, owner contacts, and review signals into outreach-ready leads.
5. Keep source coverage and failure state visible for every run.

## Non-Goals

1. Building a large workflow or queueing system inside Scout.
2. Treating the TUI as the primary system of record.
3. Using Linear or another external tool as the canonical database.
4. Expanding source count before merge quality is reliable.
5. Shipping complex scoring, valuation, or recommendation systems.

## Primary Users

1. The operator who runs market queries and prepares lead datasets.
2. The partner who reviews leads and starts owner conversations from the database.

## Canonical Output Today

1. `Query`
2. `Business`
3. `Listing`
4. `MarketDataset`

## Canonical Output Target

1. `Lead`
2. `OwnerContact`
3. Supporting review and source signals tied back to canonical businesses/listings

## Definition Of Success

1. A query can be rerun safely with idempotent persistence.
2. Businesses and listings land in the database with clear provenance.
3. Owner contacts and review signals can be joined to the right business.
4. Partners can review one merged lead table and begin outreach.
