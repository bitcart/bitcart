from queue import Queue

import pytest

from api import events


@pytest.fixture
def empty_event_handler():
    return events.EventHandler()


@pytest.fixture
def event_handler():
    return events.EventHandler(events={"test_event": {"params": {"param1", "param2"}, "handlers": []}})


def test_add_event_handler(empty_event_handler, event_handler):
    def func(event, event_data):
        pass

    assert not empty_event_handler.add_handler("test_event", func)
    assert not empty_event_handler.events
    assert event_handler.add_handler("test_event", func)
    assert len(event_handler.events["test_event"]["handlers"]) == 1
    assert event_handler.events["test_event"]["handlers"][0] == func

    @event_handler.on("invalid_event")
    def func2(event, event_data):
        pass

    assert "invalid_event" not in event_handler.events
    event_handler.add_event("invalid_event", {"params": {"id"}, "handlers": []})
    assert event_handler.add_handler("invalid_event", func2)
    assert len(event_handler.events["invalid_event"]["handlers"]) == 1
    assert event_handler.events["invalid_event"]["handlers"][0] == func2


@pytest.mark.anyio
async def test_process_message(event_handler):
    queue = Queue()

    async def handler(event, event_data):
        queue.put(event_data)

    event_handler.add_handler("test_event", handler)
    await events.process_message("test", event_handler)
    assert queue.empty()
    await events.process_message({"event": "invalid_event", "data": {}}, event_handler)
    assert queue.empty()
    await events.process_message({"event": "test_event", "data": {"test": "test"}}, event_handler)
    assert queue.empty()
    sample_data = {"param1": 1, "param2": 2}
    await events.process_message({"event": "test_event", "data": sample_data}, event_handler)
    assert queue.qsize() == 1
    assert queue.get() == sample_data
