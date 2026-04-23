"""Tests for graph/config_io.py — the plumbing behind the live-edit drawer.

Critical invariants:

- YAML round-trip preserves unknown top-level sections (forks add
  these; silently dropping them on save would be a footgun).
- ``apply_updates_to_yaml`` mutates only the keys you pass and leaves
  siblings alone.
- ``validate_config_dict`` catches range / type errors before disk
  writes.
- ``read_soul`` / ``write_soul`` handles the dual-location contract
  (/sandbox/SOUL.md as runtime, config/SOUL.md as source).
- ``list_gateway_models`` returns a readable error message rather
  than raising — the UI shows this string directly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest


# ── YAML round-trip ──────────────────────────────────────────────────────────


def test_yaml_round_trip_preserves_unknown_keys(tmp_path: Path) -> None:
    """Forks add custom top-level sections (the shipped YAML already
    has ``memory`` and ``skills`` that the dataclass doesn't model).
    Round-tripping through load_yaml_doc + save_yaml_doc must leave
    them intact."""
    from graph import config_io

    yaml_path = tmp_path / "langgraph-config.yaml"
    yaml_path.write_text(
        "model:\n"
        "  name: test-model\n"
        "  temperature: 0.5\n"
        "memory:\n"
        "  path: /custom/memory\n"
        "  max_sessions: 42\n"
        "custom_section:\n"
        "  arbitrary_key: arbitrary_value\n"
    )

    doc = config_io.load_yaml_doc(yaml_path)
    config_io.save_yaml_doc(doc, yaml_path)

    reloaded = config_io.load_yaml_doc(yaml_path)
    assert reloaded["memory"]["path"] == "/custom/memory"
    assert reloaded["memory"]["max_sessions"] == 42
    assert reloaded["custom_section"]["arbitrary_key"] == "arbitrary_value"


def test_apply_updates_merges_shallowly(tmp_path: Path) -> None:
    """Updating model.temperature must NOT clobber model.name or
    other model.* fields."""
    from graph import config_io

    yaml_path = tmp_path / "c.yaml"
    yaml_path.write_text(
        "model:\n"
        "  name: original-model\n"
        "  temperature: 0.1\n"
        "  api_base: http://original\n"
    )

    doc = config_io.load_yaml_doc(yaml_path)
    config_io.apply_updates_to_yaml(doc, {"model": {"temperature": 0.9}})
    config_io.save_yaml_doc(doc, yaml_path)

    reloaded = config_io.load_yaml_doc(yaml_path)
    assert reloaded["model"]["name"] == "original-model"
    assert reloaded["model"]["api_base"] == "http://original"
    assert reloaded["model"]["temperature"] == 0.9


def test_apply_updates_adds_missing_sections(tmp_path: Path) -> None:
    from graph import config_io

    yaml_path = tmp_path / "c.yaml"
    yaml_path.write_text("model:\n  name: x\n")
    doc = config_io.load_yaml_doc(yaml_path)

    config_io.apply_updates_to_yaml(
        doc,
        {"middleware": {"audit": True, "memory": False}},
    )

    assert doc["middleware"]["audit"] is True
    assert doc["middleware"]["memory"] is False
    assert doc["model"]["name"] == "x"


def test_apply_updates_nested_worker(tmp_path: Path) -> None:
    """subagents.worker.tools is a list, subagents.worker.enabled
    is a bool — both must land in the right nested slot."""
    from graph import config_io

    yaml_path = tmp_path / "c.yaml"
    yaml_path.write_text("subagents:\n  worker:\n    enabled: false\n")
    doc = config_io.load_yaml_doc(yaml_path)

    config_io.apply_updates_to_yaml(
        doc,
        {"subagents": {"worker": {"enabled": True, "tools": ["echo", "calculator"]}}},
    )

    assert doc["subagents"]["worker"]["enabled"] is True
    assert list(doc["subagents"]["worker"]["tools"]) == ["echo", "calculator"]


# ── config_to_dict ───────────────────────────────────────────────────────────


def test_config_to_dict_mirrors_yaml_shape() -> None:
    """The UI works with the dict shape; the YAML schema uses the
    same paths. Keep them in lockstep so round-tripping through
    apply_updates_to_yaml works without path rewrites."""
    from graph.config import LangGraphConfig
    from graph.config_io import config_to_dict

    cfg = LangGraphConfig()
    d = config_to_dict(cfg)

    # Top-level schema surface
    assert set(d.keys()) == {"model", "subagents", "middleware", "knowledge"}
    assert d["model"]["name"] == cfg.model_name
    assert d["model"]["temperature"] == cfg.temperature
    assert d["subagents"]["worker"]["tools"] == list(cfg.worker.tools)
    assert d["middleware"]["audit"] == cfg.audit_middleware
    assert d["knowledge"]["top_k"] == cfg.knowledge_top_k


# ── validate_config_dict ─────────────────────────────────────────────────────


@pytest.mark.parametrize("bad_value,expected_error_fragment", [
    ({"model": {"temperature": 3.0}}, "temperature"),
    ({"model": {"temperature": -0.1}}, "temperature"),
    ({"model": {"max_tokens": 0}}, "max_tokens"),
    ({"model": {"max_iterations": 0}}, "max_iterations"),
    ({"subagents": {"worker": {"max_turns": 0}}}, "max_turns"),
    ({"subagents": {"worker": {"tools": "not-a-list"}}}, "list"),
    ({"knowledge": {"top_k": 0}}, "top_k"),
])
def test_validate_rejects_bad_values(bad_value, expected_error_fragment):
    from graph.config_io import validate_config_dict
    ok, err = validate_config_dict(bad_value)
    assert not ok
    assert expected_error_fragment in err


def test_validate_accepts_happy_path():
    from graph.config_io import config_to_dict, validate_config_dict
    from graph.config import LangGraphConfig

    ok, err = validate_config_dict(config_to_dict(LangGraphConfig()))
    assert ok, err


# ── SOUL.md dual-path ────────────────────────────────────────────────────────


def test_read_soul_falls_back_to_source(monkeypatch, tmp_path: Path) -> None:
    """When /sandbox/SOUL.md doesn't exist (local dev), fall through
    to the repo config dir so drawer edits are still visible."""
    from graph import config_io

    # Point the runtime path at an unreachable location so the source
    # fallback is exercised.
    fake_runtime = tmp_path / "nonexistent" / "SOUL.md"
    fake_source = tmp_path / "SOUL-source.md"
    fake_source.write_text("from source", encoding="utf-8")

    monkeypatch.setattr(config_io, "SOUL_RUNTIME_PATH", fake_runtime)
    monkeypatch.setattr(config_io, "SOUL_SOURCE_PATH", fake_source)

    assert config_io.read_soul() == "from source"


def test_read_soul_prefers_runtime(monkeypatch, tmp_path: Path) -> None:
    from graph import config_io

    runtime = tmp_path / "runtime" / "SOUL.md"
    runtime.parent.mkdir()
    runtime.write_text("runtime wins", encoding="utf-8")
    source = tmp_path / "SOUL-source.md"
    source.write_text("source loses", encoding="utf-8")

    monkeypatch.setattr(config_io, "SOUL_RUNTIME_PATH", runtime)
    monkeypatch.setattr(config_io, "SOUL_SOURCE_PATH", source)

    assert config_io.read_soul() == "runtime wins"


def test_write_soul_writes_source_always(monkeypatch, tmp_path: Path) -> None:
    """The source-of-truth write (config/SOUL.md) must always succeed;
    the runtime write is best-effort (skipped when /sandbox missing)."""
    from graph import config_io

    # Runtime points at a path whose parent doesn't exist — should skip
    # gracefully.
    runtime = tmp_path / "no-sandbox-here" / "SOUL.md"
    source = tmp_path / "src" / "SOUL.md"

    monkeypatch.setattr(config_io, "SOUL_RUNTIME_PATH", runtime)
    monkeypatch.setattr(config_io, "SOUL_SOURCE_PATH", source)

    written = config_io.write_soul("hello world")
    assert source in written
    assert runtime not in written
    assert source.read_text() == "hello world"


def test_write_soul_writes_both_when_runtime_parent_exists(
    monkeypatch, tmp_path: Path,
) -> None:
    from graph import config_io

    runtime_dir = tmp_path / "sandbox"
    runtime_dir.mkdir()
    runtime = runtime_dir / "SOUL.md"
    source = tmp_path / "src" / "SOUL.md"

    monkeypatch.setattr(config_io, "SOUL_RUNTIME_PATH", runtime)
    monkeypatch.setattr(config_io, "SOUL_SOURCE_PATH", source)

    written = config_io.write_soul("dual write")
    assert runtime in written
    assert source in written
    assert runtime.read_text() == "dual write"
    assert source.read_text() == "dual write"


# ── Gateway model listing ────────────────────────────────────────────────────


def test_list_gateway_models_success(monkeypatch):
    from graph import config_io

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "data": [
            {"id": "model-b"},
            {"id": "model-a"},
            {"id": "model-c"},
        ],
    }

    fake_client = MagicMock()
    fake_client.__enter__ = lambda self: fake_client
    fake_client.__exit__ = lambda *args: None
    fake_client.get.return_value = fake_response

    monkeypatch.setattr("httpx.Client", lambda **kw: fake_client)

    models, err = config_io.list_gateway_models("http://gateway:4000/v1", "test-key")
    assert err == ""
    assert models == ["model-a", "model-b", "model-c"]  # sorted
    called_url = fake_client.get.call_args[0][0]
    assert called_url == "http://gateway:4000/v1/models"


def test_list_gateway_models_empty_base_returns_error():
    from graph.config_io import list_gateway_models

    models, err = list_gateway_models("", "key")
    assert models == []
    assert "api_base" in err


def test_list_gateway_models_http_error(monkeypatch):
    from graph import config_io

    fake_client = MagicMock()
    fake_client.__enter__ = lambda self: fake_client
    fake_client.__exit__ = lambda *args: None
    fake_client.get.side_effect = httpx.ConnectError("no route to host")

    monkeypatch.setattr("httpx.Client", lambda **kw: fake_client)

    models, err = config_io.list_gateway_models("http://bad-host/v1")
    assert models == []
    assert "connection failed" in err


def test_list_gateway_models_bad_status(monkeypatch):
    from graph import config_io

    fake_response = MagicMock()
    fake_response.status_code = 401
    fake_response.text = "unauthorized"

    fake_client = MagicMock()
    fake_client.__enter__ = lambda self: fake_client
    fake_client.__exit__ = lambda *args: None
    fake_client.get.return_value = fake_response

    monkeypatch.setattr("httpx.Client", lambda **kw: fake_client)

    models, err = config_io.list_gateway_models("http://x/v1", "bad-key")
    assert models == []
    assert "401" in err


# ── list_available_tools ─────────────────────────────────────────────────────


def test_list_available_tools_returns_starter_set():
    from graph.config_io import list_available_tools

    names = list_available_tools()
    # Lock in the template's starter set — forks replace these but
    # the drawer's CheckboxGroup populates from this call, so the
    # contract is "return tool names in a stable list".
    assert "echo" in names
    assert "calculator" in names
    assert "current_time" in names
    assert all(isinstance(n, str) for n in names)
