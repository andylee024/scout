"""Google Maps DataSource."""

from __future__ import annotations

from scout.pipeline.data_sources.base import DataSource, NormalizedBatch
from scout.pipeline.models.business import Business
from scout.pipeline.models.query import Query
from data_sources.maps.google_maps import GoogleMapsTool


class GoogleMapsDataSource(DataSource):
    name = "google_maps"

    def __init__(self) -> None:
        self.tool = GoogleMapsTool()

    def fetch(self, query: Query) -> dict[str, object]:
        payload = self.tool.search(
            industry=query.industry,
            location=query.location,
            max_results=query.max_results,
            use_cache=query.use_cache,
        )
        return dict(payload)

    def normalize(self, raw: dict[str, object], query: Query) -> NormalizedBatch:
        businesses: list[Business] = []
        for item in raw.get("results", []) or []:
            if not isinstance(item, dict):
                continue
            businesses.append(
                Business(
                    name=str(item.get("name", "")).strip(),
                    place_id=str(item.get("place_id", "")).strip(),
                    address=str(item.get("address", "")),
                    phone=str(item.get("phone", "")),
                    website=str(item.get("website", "")),
                    category=str(item.get("category", query.industry)),
                    location=str(item.get("address", "")),
                    rating=_to_float(item.get("rating")),
                    reviews=_to_int(item.get("reviews")),
                    source=self.name,
                )
            )

        return NormalizedBatch(
            businesses=[business for business in businesses if business.name],
            listings=[],
            signals={
                "total_found": raw.get("total_found", len(businesses)),
                "location": raw.get("location", query.location),
            },
        )


def _to_float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
