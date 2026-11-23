"""SSRF-aware page fetch — text only, no JS execution."""

from __future__ import annotations

import ipaddress
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.agents.tool_contracts import ToolResult

MAX_BYTES = 500_000
TIMEOUT = 12.0


def _is_private_host(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return True
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return True
    return False


def fetch_page(url: str) -> ToolResult:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return ToolResult(
            tool="fetch_page",
            ok=False,
            message_fa="فقط http/https مجاز است.",
            error_code="INVALID_URL",
        )
    host = parsed.hostname or ""
    if not host or _is_private_host(host):
        return ToolResult(
            tool="fetch_page",
            ok=False,
            message_fa="آدرس خصوصی یا غیرمجاز مسدود شد (SSRF).",
            error_code="SSRF_BLOCKED",
        )
    try:
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": "NOVA-ExportResearch/1.0"})
        if r.status_code >= 400:
            return ToolResult(
                tool="fetch_page",
                ok=False,
                message_fa=f"صفحه در دسترس نبود ({r.status_code}).",
                error_code="PAGE_UNAVAILABLE",
                provenance=[{"url": url, "status": r.status_code}],
            )
        raw = r.content[:MAX_BYTES]
        # strip crude tags
        text = raw.decode(r.encoding or "utf-8", errors="replace")
        text = (
            text.replace("<script", " <!--")
            .replace("<style", " <!--")
        )
        # very light HTML strip
        import re

        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()[:12000]
        return ToolResult(
            tool="fetch_page",
            ok=True,
            message_fa="متن صفحه استخراج شد.",
            data={
                "url": url,
                "text": text,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "status_code": r.status_code,
            },
            provenance=[
                {
                    "url": url,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "publisher": host,
                }
            ],
            spent={"page": 1},
        )
    except Exception as exc:
        return ToolResult(
            tool="fetch_page",
            ok=False,
            message_fa=f"خواندن صفحه ناموفق ({type(exc).__name__}).",
            error_code="PAGE_FETCH_ERROR",
        )
