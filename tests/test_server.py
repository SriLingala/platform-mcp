"""
Smoke tests for the platform-mcp server.

These don't exercise the full MCP stdio transport — they prove that:
  - the module imports without side effects,
  - each tool function returns the expected shape for valid input,
  - each tool raises ValueError for unknown input (so FastMCP surfaces it
    as a proper MCP error to the client),
  - the FastMCP instance has every advertised tool registered.

A green test run here is enough to know the README's "run it locally in
one command" promise still holds against whatever mcp version pip resolves.
"""

from __future__ import annotations

import asyncio

import pytest

from platform_mcp import server

# ---- list_blueprints -------------------------------------------------------

def test_list_blueprints_returns_all_entries() -> None:
    out = server.list_blueprints()
    assert isinstance(out, list)
    assert len(out) == len(server.BLUEPRINTS)
    for entry in out:
        assert set(entry.keys()) == {"name", "summary", "url"}
        assert entry["url"].startswith("https://github.com/")


# ---- describe_blueprint ----------------------------------------------------

def test_describe_blueprint_known_name() -> None:
    out = server.describe_blueprint("aks-platform")
    assert out["name"] == "aks-platform"
    assert "AKS" in out["stack"]
    assert out["url"] == "https://github.com/SriLingala/aks-platform"


def test_describe_blueprint_unknown_name_raises() -> None:
    with pytest.raises(ValueError, match="Unknown blueprint"):
        server.describe_blueprint("does-not-exist")  # type: ignore[arg-type]


# ---- describe_pattern ------------------------------------------------------

def test_describe_pattern_known() -> None:
    out = server.describe_pattern("workload-identity")
    assert out["pattern"] == "workload-identity"
    assert "Workload Identity" in out["description"]


def test_describe_pattern_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown pattern"):
        server.describe_pattern("invalid")  # type: ignore[arg-type]


# ---- get_runbook -----------------------------------------------------------

def test_get_runbook_known() -> None:
    out = server.get_runbook("argocd-out-of-sync")
    assert out["scenario"] == "argocd-out-of-sync"
    assert isinstance(out["steps"], list)
    assert all(isinstance(step, str) for step in out["steps"])
    assert len(out["steps"]) >= 3


def test_get_runbook_unknown_raises() -> None:
    with pytest.raises(ValueError, match="No runbook"):
        server.get_runbook("nope")  # type: ignore[arg-type]


# ---- check_compliance ------------------------------------------------------

def test_check_compliance_known() -> None:
    out = server.check_compliance("namespace")
    assert out["component"] == "namespace"
    checks = out["checks"]
    assert isinstance(checks, list)
    for entry in checks:
        assert set(entry.keys()) == {"check", "verify"}


def test_check_compliance_unknown_raises() -> None:
    with pytest.raises(ValueError, match="No compliance checks"):
        server.check_compliance("router")  # type: ignore[arg-type]


# ---- FastMCP tool registration --------------------------------------------

def test_every_documented_tool_is_registered() -> None:
    """Catch the class of bug where a new tool is implemented but the
    @mcp.tool() decorator is forgotten — the README would lie."""
    expected = {
        "list_blueprints",
        "describe_blueprint",
        "describe_pattern",
        "get_runbook",
        "check_compliance",
    }
    registered = {tool.name for tool in asyncio.run(server.mcp.list_tools())}
    assert expected <= registered, f"missing tools: {expected - registered}"
