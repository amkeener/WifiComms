"""Agent Messenger - UDP multicast messaging for Claude agents."""

__version__ = "0.1.0"

from .messenger import AgentMessenger
from .protocol import Message, MessageType

__all__ = ["AgentMessenger", "Message", "MessageType", "__version__"]
