import asyncio

import pytest

from backend.app.state import PendingSignalRegistry, SharedState


def test_shared_state_update_and_get():
    state = SharedState()
    state.update({"a": 1})
    assert state.get() == {"a": 1}


@pytest.mark.asyncio
async def test_pending_signal_registry_resolve():
    registry = PendingSignalRegistry()
    loop = asyncio.get_event_loop()
    future = registry.register("sig1", {"strategy": "X"}, loop)
    assert registry.list_pending() == [{"strategy": "X"}]

    assert registry.resolve("sig1", "approve") is True
    assert await future == "approve"
    assert registry.list_pending() == []


@pytest.mark.asyncio
async def test_pending_signal_registry_resolve_twice_returns_false():
    registry = PendingSignalRegistry()
    loop = asyncio.get_event_loop()
    registry.register("sig1", {}, loop)
    assert registry.resolve("sig1", "approve") is True
    assert registry.resolve("sig1", "reject") is False


def test_pending_signal_registry_resolve_unknown_returns_false():
    registry = PendingSignalRegistry()
    assert registry.resolve("unknown", "approve") is False
