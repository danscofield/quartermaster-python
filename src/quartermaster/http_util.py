"""HTTP client helpers."""

from __future__ import annotations

import ssl

import httpx

from quartermaster.config import TLSConfig


def build_http_client(
    *,
    tls: TLSConfig | None = None,
    timeout: float = 30.0,
) -> httpx.Client:
    """Build an httpx client with optional mTLS configuration."""
    verify: ssl.SSLContext | str | bool = True
    cert: tuple[str, str] | str | None = None

    if tls:
        if tls.ca_file:
            verify = tls.ca_file
        if tls.cert_file and tls.key_file:
            cert = (tls.cert_file, tls.key_file)
        elif tls.cert_file or tls.key_file:
            raise ValueError("both cert_file and key_file are required for client mTLS")

    return httpx.Client(verify=verify, cert=cert, timeout=timeout)


def parse_error_response(resp: httpx.Response) -> tuple[str | None, str | None]:
    """Extract OAuth-style error fields from a JSON response body."""
    try:
        body = resp.json()
    except ValueError:
        return None, None
    if not isinstance(body, dict):
        return None, None
    error = body.get("error")
    description = body.get("error_description") or body.get("error")
    return (
        str(error) if error is not None else None,
        str(description) if description is not None else None,
    )
