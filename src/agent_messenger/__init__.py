"""Agent Messenger - UDP multicast messaging for Claude agents."""

__version__ = "0.1.1"

from .messenger import AgentMessenger
from .protocol import Message, MessageType
from .file_transport import FileTransport

__all__ = ["AgentMessenger", "Message", "MessageType", "FileTransport", "__version__"]
