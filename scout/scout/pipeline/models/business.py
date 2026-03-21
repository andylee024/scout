"""Canonical business model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Business:
    name: str
    place_id: str = ""
    address: str = ""
    phone: str = ""
    website: str = ""
    category: str = ""
    location: str = ""
    state: str = ""
    rating: float | None = None
    reviews: int | None = None
    source: str = "google_maps"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Business":
        return cls(
            name=str(payload.get("name", "")),
            place_id=str(payload.get("place_id", "")),
            address=str(payload.get("address", "")),
            phone=str(payload.get("phone", "")),
            website=str(payload.get("website", "")),
            category=str(payload.get("category", "")),
            location=str(payload.get("location", "")),
            state=str(payload.get("state", "")),
            rating=_to_float(payload.get("rating")),
            reviews=_to_int(payload.get("reviews")),
            source=str(payload.get("source", "google_maps")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "place_id": self.place_id,
            "address": self.address,
            "phone": self.phone,
            "website": self.website,
            "category": self.category,
            "location": self.location,
            "state": self.state,
            "rating": self.rating,
            "reviews": self.reviews,
            "source": self.source,
        }


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
