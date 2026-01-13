"""Tests for the protocol module."""

import time
import pytest

from agent_messenger.protocol import (
    Message,
    MessageType,
    encode,
    decode,
    create_message,
    create_heartbeat,
    generate_uuid,
)


def test_generate_uuid():
    """UUID generation produces valid UUIDs."""
    uuid1 = generate_uuid()
    uuid2 = generate_uuid()

    # Should be strings
    assert isinstance(uuid1, str)
    assert isinstance(uuid2, str)

    # Should be unique
    assert uuid1 != uuid2

    # Should be valid UUID format (36 chars with hyphens)
    assert len(uuid1) == 36
    assert uuid1.count("-") == 4


def test_create_message():
    """create_message produces valid Message objects."""
    uuid = "test-uuid-1234"
    text = "Hello, world!"

    msg = create_message(uuid, text)

    assert msg.uuid == uuid
    assert msg.type == MessageType.MESSAGE
    assert msg.payload == text
    assert isinstance(msg.timestamp, float)
    assert msg.timestamp <= time.time()


def test_create_heartbeat():
    """create_heartbeat produces valid heartbeat Messages."""
    uuid = "test-uuid-1234"

    msg = create_heartbeat(uuid)

    assert msg.uuid == uuid
    assert msg.type == MessageType.HEARTBEAT
    assert msg.payload == ""
    assert isinstance(msg.timestamp, float)


def test_encode_decode_message():
    """Messages can be encoded and decoded correctly."""
    original = create_message("test-uuid", "Test message content")

    encoded = encode(original)
    decoded = decode(encoded)

    assert decoded.uuid == original.uuid
    assert decoded.type == original.type
    assert decoded.payload == original.payload
    assert decoded.timestamp == original.timestamp


def test_encode_decode_heartbeat():
    """Heartbeat messages can be encoded and decoded correctly."""
    original = create_heartbeat("test-uuid")

    encoded = encode(original)
    decoded = decode(encoded)

    assert decoded.uuid == original.uuid
    assert decoded.type == MessageType.HEARTBEAT
    assert decoded.payload == ""


def test_encode_produces_bytes():
    """encode() returns bytes."""
    msg = create_message("uuid", "text")
    encoded = encode(msg)

    assert isinstance(encoded, bytes)


def test_decode_handles_utf8():
    """decode() handles UTF-8 content correctly."""
    msg = create_message("uuid", "Hello 你好 مرحبا 🎉")
    encoded = encode(msg)
    decoded = decode(encoded)

    assert decoded.payload == "Hello 你好 مرحبا 🎉"


def test_message_to_dict():
    """Message.to_dict() produces correct dictionary."""
    msg = Message(
        uuid="test-uuid",
        type=MessageType.MESSAGE,
        payload="Hello",
        timestamp=1234567890.123,
    )

    d = msg.to_dict()

    assert d == {
        "uuid": "test-uuid",
        "type": "message",
        "payload": "Hello",
        "timestamp": 1234567890.123,
    }


def test_message_from_dict():
    """Message.from_dict() creates correct Message."""
    d = {
        "uuid": "test-uuid",
        "type": "heartbeat",
        "payload": "",
        "timestamp": 1234567890.123,
    }

    msg = Message.from_dict(d)

    assert msg.uuid == "test-uuid"
    assert msg.type == MessageType.HEARTBEAT
    assert msg.payload == ""
    assert msg.timestamp == 1234567890.123
