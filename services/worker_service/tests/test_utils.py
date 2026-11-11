"""Тесты утилит worker_service."""

from app.core.utils import sanitize_url


def test_sanitize_url_removes_query_params() -> None:
    url = "https://n8n.example.com/webhook/abc123?token=secret"

    assert sanitize_url(url) == "https://n8n.example.com/webhook/abc123"


def test_sanitize_url_removes_query_and_fragment() -> None:
    url = "https://n8n.example.com/webhook/abc123?token=secret#step-1"

    assert sanitize_url(url) == "https://n8n.example.com/webhook/abc123"


def test_sanitize_url_keeps_scheme_host_port_and_path() -> None:
    url = "http://n8n.example.com:9000/webhook/abc123?token=secret"

    assert sanitize_url(url) == "http://n8n.example.com:9000/webhook/abc123"


def test_sanitize_url_removes_userinfo() -> None:
    url = "https://user:pass@n8n.example.com:8443/webhook/abc123?token=secret"

    assert sanitize_url(url) == "https://n8n.example.com:8443/webhook/abc123"


def test_sanitize_url_handles_invalid_url_safely() -> None:
    url = "http://n8n.example.com:bad-port/webhook?token=secret"

    assert sanitize_url(url) == "http://n8n.example.com/webhook"
