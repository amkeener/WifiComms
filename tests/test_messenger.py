"""Tests for the messenger module."""

import time
import threading
import pytest

from agent_messenger.messenger import AgentMessenger


def test_messenger_creates_uuid():
    """AgentMessenger auto-generates UUID if not provided."""
    m = AgentMessenger()
    assert m.uuid is not None
    assert len(m.uuid) == 36


def test_messenger_uses_provided_uuid():
    """AgentMessenger uses provided UUID."""
    m = AgentMessenger(uuid="custom-uuid-1234")
    assert m.uuid == "custom-uuid-1234"


def test_messenger_start_stop():
    """Messenger can start and stop cleanly."""
    m = AgentMessenger()
    m.start()
    time.sleep(0.1)
    m.stop()
    # Should not raise


def test_messenger_context_manager():
    """Messenger works as context manager."""
    with AgentMessenger() as m:
        assert m._running
        time.sleep(0.1)
    assert not m._running


def test_messenger_handler_registration():
    """Message handlers can be registered."""
    m = AgentMessenger()

    received = []

    @m.on_message
    def handler(uuid, text):
        received.append((uuid, text))

    assert handler in m._handlers


def test_messenger_add_handler():
    """add_handler() registers handlers."""
    m = AgentMessenger()

    received = []

    def handler(uuid, text):
        received.append((uuid, text))

    m.add_handler(handler)
    assert handler in m._handlers


def test_messenger_send_requires_start():
    """send() raises error if not started."""
    m = AgentMessenger()
    with pytest.raises(RuntimeError, match="not started"):
        m.send("test")


def test_messenger_communication():
    """Two messengers can communicate."""
    received1 = []
    received2 = []

    m1 = AgentMessenger()
    m2 = AgentMessenger()

    @m1.on_message
    def handler1(uuid, text):
        received1.append((uuid, text))

    @m2.on_message
    def handler2(uuid, text):
        received2.append((uuid, text))

    m1.start()
    m2.start()

    time.sleep(0.2)  # Allow sockets to initialize

    m1.send("Hello from m1")
    time.sleep(0.2)  # Allow message to propagate

    m2.send("Hello from m2")
    time.sleep(0.2)

    m1.stop()
    m2.stop()

    # m2 should have received m1's message
    assert any(text == "Hello from m1" for uuid, text in received2)
    # m1 should have received m2's message
    assert any(text == "Hello from m2" for uuid, text in received1)


def test_messenger_peer_discovery():
    """Messengers discover each other as peers."""
    m1 = AgentMessenger()
    m2 = AgentMessenger()

    m1.start()
    m2.start()

    # Wait for heartbeats
    time.sleep(1.0)

    peers1 = m1.get_peers()
    peers2 = m2.get_peers()

    m1.stop()
    m2.stop()

    # Each should see the other as a peer
    assert m2.uuid in peers1
    assert m1.uuid in peers2


def test_messenger_does_not_receive_own_messages():
    """Messenger does not trigger handler for own messages."""
    received = []

    m = AgentMessenger()

    @m.on_message
    def handler(uuid, text):
        received.append((uuid, text))

    m.start()
    time.sleep(0.1)

    m.send("My own message")
    time.sleep(0.2)

    m.stop()

    # Should not have received own message
    assert not any(uuid == m.uuid for uuid, text in received)


def test_get_active_peer_count():
    """get_active_peer_count returns correct count."""
    m1 = AgentMessenger()
    m2 = AgentMessenger()
    m3 = AgentMessenger()

    m1.start()
    m2.start()
    m3.start()

    time.sleep(1.0)

    # Each messenger should see 2 peers
    assert m1.get_active_peer_count() == 2
    assert m2.get_active_peer_count() == 2
    assert m3.get_active_peer_count() == 2

    m1.stop()
    m2.stop()
    m3.stop()
