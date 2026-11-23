"""Buyer search — source-backed candidates, no fabricated contacts."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.providers.keyed import KeyedTavilySearch


def test_tavily_search_buyers_builds_candidates_without_contacts():
    payload = {
        "results": [
            {
                "url": "https://www.acme-import.de/pistachio",
                "title": "ACME Import GmbH - Food importers",
                "content": "German importer of nuts and dried fruit including pistachio.",
            },
            {
                "url": "https://www.acme-import.de/about",
                "title": "About ACME",
                "content": "duplicate host should be skipped",
            },
            {
                "url": "https://buyers.example.org/list",
                "title": "Example Buyers Directory | Trade",
                "content": "Directory listing of food buyers in DE.",
            },
        ]
    }

    class FakeResp:
        status_code = 200

        def json(self):
            return payload

    search = KeyedTavilySearch(api_key="test-key")
    with patch("httpx.Client") as client_cls:
        http = MagicMock()
        http.__enter__.return_value = http
        http.post.return_value = FakeResp()
        client_cls.return_value = http

        result = search.search_buyers("pistachio", "DE")

    assert result.ok is True
    assert len(result.buyers) == 2
    assert all(b.contact is None for b in result.buyers)
    assert all(b.verification_status == "needs_review" for b in result.buyers)
    assert all(b.website for b in result.buyers)
    assert all(b.sources for b in result.buyers)
    assert "ACME Import GmbH" in result.buyers[0].company_name


def test_tavily_search_buyers_empty_when_no_hits():
    class FakeResp:
        status_code = 200

        def json(self):
            return {"results": []}

    search = KeyedTavilySearch(api_key="test-key")
    with patch("httpx.Client") as client_cls:
        http = MagicMock()
        http.__enter__.return_value = http
        http.post.return_value = FakeResp()
        client_cls.return_value = http
        result = search.search_buyers("x", "AE")

    assert result.ok is False
    assert result.buyers == []
    assert result.error_code == "NO_BUYERS"
