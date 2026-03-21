-- Supabase schema for Scout data pipeline
-- Run this in the Supabase SQL editor after creating the businesses/contacts tables.

ALTER TABLE businesses
  ADD COLUMN IF NOT EXISTS place_id text;

CREATE INDEX IF NOT EXISTS idx_businesses_place_id
  ON businesses (place_id);

CREATE OR REPLACE VIEW leads AS
  SELECT b.id, b.source, b.name, b.place_id, b.address, b.city, b.state,
         b.phone, b.website, b.category, b.rating, b.reviews,
         c.first_name, c.last_name, c.title AS contact_title,
         c.email, c.linkedin, c.intent, c.why, c.signals,
         b.created_at, b.updated_at
  FROM businesses b
  LEFT JOIN contacts c ON c.business_id = b.id;
