"""Tests for supabase_service helpers, Contact model, and CSV round-trips."""

from __future__ import annotations

import csv
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scout.pipeline.models.contact import Contact
from scout.pipeline.supabase_service import (
    _extract_city,
    _extract_domain,
    _extract_state,
    ingest_contacts,
    upload_businesses,
    upload_contacts,
    verify,
)


# -------------------------------------------------------------------
# Helper unit tests
# -------------------------------------------------------------------


class TestExtractCity:
    def test_full_address(self):
        assert _extract_city("123 Main St, Houston, TX 77001, USA") == "Houston"

    def test_city_state_only(self):
        assert _extract_city("Los Angeles, CA") == "Los Angeles"

    def test_city_state_country(self):
        assert _extract_city("Denver, CO, USA") == "Denver"

    def test_empty(self):
        assert _extract_city("") == ""

    def test_no_state_token(self):
        # Falls back to second-to-last part
        assert _extract_city("Some Place, Somewhere") == "Some Place"


class TestExtractState:
    def test_full_address(self):
        assert _extract_state("123 Main St, Houston, TX 77001, USA") == "TX"

    def test_city_state(self):
        assert _extract_state("Houston, TX") == "TX"

    def test_city_state_country(self):
        assert _extract_state("Denver, CO, USA") == "CO"

    def test_empty(self):
        assert _extract_state("") == ""

    def test_lowercase(self):
        assert _extract_state("Houston, tx") == "TX"


class TestExtractDomain:
    def test_full_url(self):
        assert _extract_domain("https://www.example.com/page") == "example.com"

    def test_bare_domain(self):
        assert _extract_domain("example.com") == "example.com"

    def test_http(self):
        assert _extract_domain("http://foo.bar.com") == "foo.bar.com"

    def test_www_stripped(self):
        assert _extract_domain("https://www.test.io") == "test.io"

    def test_empty(self):
        assert _extract_domain("") == ""


# -------------------------------------------------------------------
# Contact model tests
# -------------------------------------------------------------------


class TestContactFromCsvRow:
    def test_maps_clodo_headers(self):
        row = {
            "First Name": "John",
            "Last Name": "Doe",
            "Title": "CEO",
            "Company": "Acme Corp",
            "Email": "john@acme.com",
            "LinkedIn": "https://linkedin.com/in/john",
            "Website": "https://acme.com",
            "Intent": "high",
            "City": "Houston",
            "State": "TX",
            "Why": "Growing market",
            "Signals": "hiring",
        }
        c = Contact.from_csv_row(row)
        assert c.first_name == "John"
        assert c.last_name == "Doe"
        assert c.email == "john@acme.com"
        assert c.state == "TX"
        assert c.source == "clodo"

    def test_missing_fields_default_empty(self):
        c = Contact.from_csv_row({"First Name": "Jane"})
        assert c.first_name == "Jane"
        assert c.last_name == ""
        assert c.email == ""


class TestContactToSupabaseRow:
    def test_includes_all_fields(self):
        c = Contact(first_name="A", last_name="B", email="a@b.com", source="clodo")
        row = c.to_supabase_row()
        assert row["first_name"] == "A"
        assert row["email"] == "a@b.com"
        assert "business_id" not in row  # None → excluded

    def test_includes_business_id_when_set(self):
        c = Contact(email="x@y.com", business_id="uuid-123")
        row = c.to_supabase_row()
        assert row["business_id"] == "uuid-123"


# -------------------------------------------------------------------
# CSV round-trip tests
# -------------------------------------------------------------------


class TestIngestContacts:
    def test_round_trip(self, tmp_path: Path):
        clodo = tmp_path / "clodo.csv"
        clodo.write_text(
            "First Name,Last Name,Email,Company,State\n"
            "Alice,Smith,alice@co.com,AliceCo,CA\n"
            "Bob,Jones,bob@co.com,BobCo,TX\n"
        )
        out = tmp_path / "clean.csv"
        result = ingest_contacts(str(clodo), output=str(out))
        assert result == str(out)

        with open(out) as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 2
        assert rows[0]["first_name"] == "Alice"
        assert rows[1]["state"] == "TX"


class TestUploadBusinesses:
    def test_uploads_csv_rows(self, tmp_path: Path):
        csv_path = tmp_path / "biz.csv"
        csv_path.write_text(
            "source,name,place_id,address,city,state,phone,website,category,rating,reviews\n"
            "google_maps,Acme Fire,place-1,123 Main,Houston,TX,555-1234,acme.com,fire,4.5,100\n"
        )
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        with patch("scout.pipeline.supabase_service._get_client", return_value=mock_client):
            count = upload_businesses(str(csv_path))

        assert count == 1
        mock_client.table.assert_called_with("businesses")
        upserted_rows = mock_table.upsert.call_args[0][0]
        assert upserted_rows[0]["name"] == "Acme Fire"
        assert upserted_rows[0]["place_id"] == "place-1"
        assert upserted_rows[0]["rating"] == 4.5


class TestUploadContacts:
    def test_uploads_csv_rows(self, tmp_path: Path):
        csv_path = tmp_path / "contacts.csv"
        csv_path.write_text(
            "first_name,last_name,email,company,city,state,source\n"
            "Jane,Doe,jane@co.com,JaneCo,Austin,TX,clodo\n"
        )
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[])

        with patch("scout.pipeline.supabase_service._get_client", return_value=mock_client):
            count = upload_contacts(str(csv_path))

        assert count == 1
        mock_client.table.assert_called_with("contacts")


class TestVerify:
    def test_returns_count_and_samples(self):
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        # Chain for count query
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_select.limit.return_value = mock_select
        count_resp = MagicMock(count=42, data=[])
        sample_resp = MagicMock(data=[{"id": 1, "name": "Foo"}])
        mock_select.execute.side_effect = [count_resp, sample_resp]

        with patch("scout.pipeline.supabase_service._get_client", return_value=mock_client):
            result = verify("businesses")

        assert result["table"] == "businesses"
        assert result["row_count"] == 42
        assert len(result["sample_rows"]) == 1
