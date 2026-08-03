import asyncio
import json

import pytest

from backend.app.broadcaster import Broadcaster


def test_snapshot_frame_contains_full_state():
    state = {"a": 1, "b": 2}
    broadcaster = Broadcaster(snapshot_provider=lambda: state, interval=0.01)
    frame = json.loads(broadcaster.snapshot_frame())
    assert frame["type"] == "snapshot"
    assert frame["data"] == state
    assert frame["seq"] == 1


def test_subscribe_and_unsubscribe():
    broadcaster = Broadcaster(snapshot_provider=lambda: {}, interval=0.01)
    queue = broadcaster.subscribe()
    assert queue in broadcaster._subscribers
    broadcaster.unsubscribe(queue)
    assert queue not in broadcaster._subscribers


@pytest.mark.asyncio
async def test_delta_frame_only_contains_changed_keys():
    state = {"a": 1, "b": 2}
    broadcaster = Broadcaster(snapshot_provider=lambda: state, interval=0.02)
    queue = broadcaster.subscribe()
    broadcaster.snapshot_frame()  # seeds _prev_snapshot equivalent via first read

    await broadcaster.start()
    state["a"] = 99  # only 'a' changed
    await asyncio.sleep(0.05)
    await broadcaster.stop()

    frame = json.loads(await asyncio.wait_for(queue.get(), timeout=1))
    assert frame["type"] == "delta"
    assert frame["data"] == {"a": 99}


@pytest.mark.asyncio
async def test_no_frames_sent_when_nothing_changes_and_no_heartbeat_due_yet():
    state = {"a": 1}
    broadcaster = Broadcaster(snapshot_provider=lambda: state, interval=0.02)
    queue = broadcaster.subscribe()

    await broadcaster.start()
    await asyncio.sleep(0.1)  # well under the 5s heartbeat threshold
    await broadcaster.stop()

    assert queue.empty()  # no delta (nothing changed) and no heartbeat (too soon)
