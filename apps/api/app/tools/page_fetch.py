"""SSRF-safe page fetch: pinned public DNS, checked redirects, size and type limits."""

from __future__ import annotations

import ipaddress
import re
import socket
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx

from app.agents.tool_contracts import ToolResult

MAX_BYTES = 500_000
TIMEOUT = 12.0
MAX_REDIRECTS = 3
UA = "NOVA-ExportResearch/1.0 (export intelligence; contact: local-dev)"
ALLOWED_TYPES = {
    "text/html",
    "text/plain",
    "application/xhtml+xml",
    "application/json",
    "text/xml",
    "application/xml",
}
_BLOCKED_HOSTS = {"localhost", "metadata", "metadata.google.internal"}
_INJECTION = re.compile(
    r"(ignore (all )?(previous|prior) instructions|system\s*:|you are now|"
    r"فرامین قبلی را نادیده|دستور سیستم)",
    re.I,
)


def _ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _ip_blocked(ip.ipv4_mapped)
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def resolve_public_ips(hostname: str) -> set[str]:
    host = (hostname or "").strip().lower().rstrip(".")
    if not host or host in _BLOCKED_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        raise PermissionError("blocked host")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if _ip_blocked(literal):
            raise PermissionError("blocked ip")
        return {str(literal)}
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise PermissionError("dns") from exc
    ips: set[str] = set()
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _ip_blocked(ip):
            raise PermissionError("blocked ip")
        ips.add(str(ip))
    if not ips:
        raise PermissionError("no address")
    return ips


def _confirm_public(hostname: str) -> set[str]:
    first = resolve_public_ips(hostname)
    second = resolve_public_ips(hostname)
    if first != second:
        raise PermissionError("dns rebinding")
    return first


def _ssrf(message: str = "آدرس خصوصی، حلقهٔ DNS یا تغییر مسیر ناامن مسدود شد.") -> ToolResult:
    return ToolResult(
        tool="fetch_page",
        ok=False,
        message_fa=message,
        error_code="SSRF_BLOCKED",
    )


def fetch_page(url: str) -> ToolResult:
    current = url
    seen: set[str] = set()
    for _hop in range(MAX_REDIRECTS + 1):
        parsed = urlparse(current)
        if parsed.scheme not in {"http", "https"}:
            return ToolResult(
                tool="fetch_page",
                ok=False,
                message_fa="فقط http/https مجاز است.",
                error_code="INVALID_URL",
            )
        if parsed.username or parsed.password:
            return _ssrf("آدرس دارای اطلاعات ورود مسدود شد.")
        host = parsed.hostname or ""
        try:
            _confirm_public(host)
        except PermissionError:
            return _ssrf()
        if current in seen:
            return _ssrf("حلقهٔ تغییر مسیر مسدود شد.")
        seen.add(current)
        try:
            with httpx.Client(timeout=TIMEOUT, follow_redirects=False) as client:
                response = client.get(
                    current,
                    headers={"User-Agent": UA, "Accept": "text/html,text/plain,application/json"},
                )
        except Exception as exc:
            return ToolResult(
                tool="fetch_page",
                ok=False,
                message_fa=f"خواندن صفحه ناموفق ({type(exc).__name__}).",
                error_code="PAGE_FETCH_ERROR",
            )
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location")
            if not location:
                return ToolResult(
                    tool="fetch_page",
                    ok=False,
                    message_fa="تغییر مسیر بدون مقصد بود.",
                    error_code="PAGE_UNAVAILABLE",
                )
            current = urljoin(current, location)
            continue
        if response.status_code >= 400:
            return ToolResult(
                tool="fetch_page",
                ok=False,
                message_fa=f"صفحه در دسترس نبود ({response.status_code}).",
                error_code="PAGE_UNAVAILABLE",
                provenance=[{"url": current, "status": response.status_code}],
            )
        content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
        if content_type and content_type not in ALLOWED_TYPES and not content_type.startswith("text/"):
            return ToolResult(
                tool="fetch_page",
                ok=False,
                message_fa=f"نوع محتوا مجاز نیست ({content_type}).",
                error_code="UNSUPPORTED_MEDIA",
            )
        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BYTES:
            return ToolResult(
                tool="fetch_page",
                ok=False,
                message_fa="حجم صفحه از سقف مجاز بیشتر است.",
                error_code="PAYLOAD_TOO_LARGE",
            )
        raw = response.content[:MAX_BYTES]
        text = raw.decode(response.encoding or "utf-8", errors="replace")
        text = text.replace("<script", " <!--").replace("<style", " <!--")
        text = re.sub(r"<[^>]+>", " ", text)
        text = _INJECTION.sub("[untrusted-text]", text)
        text = re.sub(r"\s+", " ", text).strip()[:12000]
        fetched_at = datetime.now(timezone.utc).isoformat()
        return ToolResult(
            tool="fetch_page",
            ok=True,
            message_fa="متن صفحه استخراج شد.",
            data={
                "url": str(response.url),
                "text": text,
                "fetched_at": fetched_at,
                "status_code": response.status_code,
                "content_type": content_type or None,
                "injection_sanitized": "[untrusted-text]" in text,
            },
            provenance=[{"url": str(response.url), "fetched_at": fetched_at, "publisher": host}],
            spent={"page": 1},
        )
    return ToolResult(
        tool="fetch_page",
        ok=False,
        message_fa="تعداد تغییر مسیر از سقف گذشت.",
        error_code="TOO_MANY_REDIRECTS",
    )
