"""Tests for scrape subprocess result parsing."""

from backend.api.job_manager import _parse_child_payload


def test_parse_child_payload_last_json_line():
    stdout = "noise\n{\"ok\": false, \"error\": \"old\"}\n{\"ok\": true, \"result\": {\"weeks\": 1}}\n"
    payload = _parse_child_payload(stdout, "", 0)
    assert payload == {"ok": True, "result": {"weeks": 1}}


def test_parse_child_payload_ignores_non_ok_dicts():
    stdout = '{"status": "running"}\n{"ok": true, "result": {}}\n'
    payload = _parse_child_payload(stdout, "", 0)
    assert payload["ok"] is True


def test_parse_child_payload_falls_back_to_exit():
    payload = _parse_child_payload("", "", 7)
    assert payload == {"ok": False, "error": "Scrape subprocess failed: exit 7"}

    payload = _parse_child_payload("not json\n", "", 1)
    assert payload["ok"] is False
    assert "not json" in payload["error"]
