"""Buyer discovery — companies only from source hits, no fabricated contacts."""

from __future__ import annotations

from app.agents.buyer_runner import candidates_from_search_hits


def test_search_hits_become_candidates_without_contacts():
    results = [
        {
            "url": "https://www.acme-import.de/pistachio",
            "title": "ACME Import GmbH - Food importers",
            "snippet": "German importer of nuts and dried fruit including pistachio.",
            "publisher": "web",
            "fetched_at": "2024-01-01T00:00:00+00:00",
            "provider": "duckduckgo_html",
        },
        {
            "url": "https://www.acme-import.de/about",
            "title": "About ACME",
            "snippet": "duplicate host should still be a separate page until verify dedupes",
            "provider": "duckduckgo_html",
        },
        {
            "url": "https://en.wikipedia.org/wiki/Pistachio",
            "title": "Pistachio",
            "snippet": "encyclopedia",
            "provider": "wikipedia_free",
        },
    ]
    buyers = candidates_from_search_hits(results, country="DE", product="pistachio", role="importer")
    assert len(buyers) == 2
    assert all(buyer.contact is None for buyer in buyers)
    assert all(buyer.sources for buyer in buyers)
    assert "ACME Import GmbH" in buyers[0].company_name
    assert all("wikipedia.org" not in (buyer.website or "") for buyer in buyers)


def test_empty_hits_produce_no_companies():
    assert candidates_from_search_hits([], country="AE", product="x", role="importer") == []
