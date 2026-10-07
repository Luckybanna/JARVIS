"""
Unit tests for the thread-safe EventBus.
"""

import threading
import time
import pytest

from app.core.events import Event, EventBus, EventType


def test_subscribe_and_publish():
    bus = EventBus()
    received_events = []

    def handler(evt: Event):
        received_events.append(evt)

    bus.subscribe(EventType.USER_INPUT_TEXT, handler)
    bus.publish(Event(event_type=EventType.USER_INPUT_TEXT, data={"text": "hello jarvis"}))

    assert len(received_events) == 1
    assert received_events[0].data["text"] == "hello jarvis"
    assert received_events[0].event_type == EventType.USER_INPUT_TEXT


def test_unsubscribe():
    bus = EventBus()
    received = []

    def handler(evt: Event):
        received.append(evt)

    bus.subscribe(EventType.MIC_LISTENING_START, handler)
    bus.publish(Event(event_type=EventType.MIC_LISTENING_START))
    assert len(received) == 1

    bus.unsubscribe(EventType.MIC_LISTENING_START, handler)
    bus.publish(Event(event_type=EventType.MIC_LISTENING_START))
    assert len(received) == 1  # No new event received


def test_global_subscribers():
    bus = EventBus()
    all_events = []

    def global_handler(evt: Event):
        all_events.append(evt)

    bus.subscribe_all(global_handler)

    bus.publish(Event(event_type=EventType.JARVIS_THINKING_START))
    bus.publish(Event(event_type=EventType.JARVIS_THINKING_STOP))

    assert len(all_events) == 2


def test_handler_exception_isolation():
    bus = EventBus()
    successful_runs = []

    def broken_handler(evt: Event):
        raise RuntimeError("Simulated listener crash")

    def safe_handler(evt: Event):
        successful_runs.append(evt)

    bus.subscribe(EventType.TTS_SPEAKING_START, broken_handler)
    bus.subscribe(EventType.TTS_SPEAKING_START, safe_handler)

    # Should not raise exception
    bus.publish(Event(event_type=EventType.TTS_SPEAKING_START))

    assert len(successful_runs) == 1


def test_multithreaded_publishing():
    bus = EventBus()
    counter = {"count": 0}
    lock = threading.Lock()

    def handler(evt: Event):
        with lock:
            counter["count"] += 1

    bus.subscribe(EventType.AVATAR_STATE_CHANGED, handler)

    def worker():
        for _ in range(50):
            bus.publish(Event(event_type=EventType.AVATAR_STATE_CHANGED))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counter["count"] == 200
