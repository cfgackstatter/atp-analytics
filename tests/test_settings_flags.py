"""Tests for env flag helpers."""

from backend.api.settings import docs_enabled, flag_enabled, force_https_enabled


def test_flag_enabled_truthy_falsey(monkeypatch):
    monkeypatch.setenv("FLAG_X", "true")
    assert flag_enabled("FLAG_X") is True
    monkeypatch.setenv("FLAG_X", "0")
    assert flag_enabled("FLAG_X") is False
    monkeypatch.delenv("FLAG_X", raising=False)
    assert flag_enabled("FLAG_X", default=True) is True


def test_force_https_and_docs_defaults(monkeypatch):
    monkeypatch.delenv("FORCE_HTTPS", raising=False)
    monkeypatch.delenv("ENABLE_DOCS", raising=False)
    assert force_https_enabled() is False
    assert docs_enabled() is True

    monkeypatch.setenv("FORCE_HTTPS", "true")
    assert force_https_enabled() is True
    assert docs_enabled() is False

    monkeypatch.setenv("ENABLE_DOCS", "true")
    assert docs_enabled() is True
