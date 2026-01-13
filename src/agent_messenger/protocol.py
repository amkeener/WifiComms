"""Message protocol for agent communication."""

import json
import time
import uuid as uuid_module
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional


class MessageType(Enum):
    """Types of messages in the protocol."""
    MESSAGE = "message"
    HEARTBEAT = "heartbeat"


@dataclass
class Message:
    """A message in the agent messenger protocol."""
    uuid: str
    type: MessageType
    payload: str
    timestamp: float

    def to_dict(self) -> dict:
        """Convert message to dictionary for serialization."""
        return {
            "uuid": self.uuid,
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Create message from dictionary."""
        return cls(
            uuid=data["uuid"],
            type=MessageType(data["type"]),
            payload=data["payload"],
            timestamp=data["timestamp"],
        )


def encode(message: Message) -> bytes:
    """Encode a message to bytes for transmission."""
    return json.dumps(message.to_dict()).encode("utf-8")


def decode(data: bytes) -> Message:
    """Decode bytes into a message."""
    parsed = json.loads(data.decode("utf-8"))
    return Message.from_dict(parsed)


def create_message(agent_uuid: str, text: str) -> Message:
    """Create a new text message."""
    return Message(
        uuid=agent_uuid,
        type=MessageType.MESSAGE,
        payload=text,
        timestamp=time.time(),
    )


def create_heartbeat(agent_uuid: str) -> Message:
    """Create a heartbeat message for peer discovery."""
    return Message(
        uuid=agent_uuid,
        type=MessageType.HEARTBEAT,
        payload="",
        timestamp=time.time(),
    )


def generate_uuid() -> str:
    """Generate a new UUID for an agent."""
    return str(uuid_module.uuid4())
