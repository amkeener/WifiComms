"""Main AgentMessenger class for agent-to-agent communication."""

import threading
import time
from typing import Callable, Dict, Optional, List

from .protocol import (
    Message,
    MessageType,
    encode,
    decode,
    create_message,
    create_heartbeat,
    generate_uuid,
)
from .network import (
    create_receiver_socket,
    create_sender_socket,
    send_multicast,
    receive_multicast,
)


# Peer discovery settings
HEARTBEAT_INTERVAL = 5.0  # seconds between heartbeats
PEER_TIMEOUT = 15.0  # seconds before peer considered offline


MessageHandler = Callable[[str, str], None]  # (uuid, text) -> None


class AgentMessenger:
    """
    UDP multicast messenger for Claude agent communication.

    Example:
        messenger = AgentMessenger()

        @messenger.on_message
        def handle(uuid, text):
            print(f"[{uuid[:8]}]: {text}")

        messenger.start()
        messenger.send("Hello!")
        # ... later ...
        messenger.stop()
    """

    def __init__(self, uuid: Optional[str] = None):
        """
        Initialize the messenger.

        Args:
            uuid: Agent UUID (auto-generated if not provided)
        """
        self.uuid = uuid or generate_uuid()
        self._handlers: List[MessageHandler] = []
        self._peers: Dict[str, float] = {}  # uuid -> last_seen_timestamp
        self._peers_lock = threading.Lock()
        self._running = False
        self._listener_thread: Optional[threading.Thread] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._receiver_socket = None
        self._sender_socket = None

    def on_message(self, handler: MessageHandler) -> MessageHandler:
        """
        Register a message handler (can be used as decorator).

        Args:
            handler: Function that takes (uuid, text) arguments

        Returns:
            The handler (for decorator use)

        Example:
            @messenger.on_message
            def handle(uuid, text):
                print(f"Message from {uuid}: {text}")
        """
        self._handlers.append(handler)
        return handler

    def add_handler(self, handler: MessageHandler) -> None:
        """
        Register a message handler (non-decorator version).

        Args:
            handler: Function that takes (uuid, text) arguments
        """
        self._handlers.append(handler)

    def start(self) -> None:
        """Start the messenger (listener and heartbeat threads)."""
        if self._running:
            return

        self._running = True
        self._receiver_socket = create_receiver_socket(timeout=1.0)
        self._sender_socket = create_sender_socket()

        # Start listener thread
        self._listener_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True,
            name=f"AgentMessenger-Listener-{self.uuid[:8]}",
        )
        self._listener_thread.start()

        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name=f"AgentMessenger-Heartbeat-{self.uuid[:8]}",
        )
        self._heartbeat_thread.start()

        # Send initial heartbeat
        self._send_heartbeat()

    def stop(self) -> None:
        """Stop the messenger gracefully."""
        self._running = False

        if self._listener_thread:
            self._listener_thread.join(timeout=2.0)
            self._listener_thread = None

        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2.0)
            self._heartbeat_thread = None

        if self._receiver_socket:
            self._receiver_socket.close()
            self._receiver_socket = None

        if self._sender_socket:
            self._sender_socket.close()
            self._sender_socket = None

    def send(self, text: str) -> None:
        """
        Send a text message to all peers.

        Args:
            text: Message text to send
        """
        if not self._sender_socket:
            raise RuntimeError("Messenger not started. Call start() first.")

        message = create_message(self.uuid, text)
        data = encode(message)
        send_multicast(self._sender_socket, data)

    def get_peers(self) -> Dict[str, float]:
        """
        Get all known peers and their last-seen timestamps.

        Returns:
            Dict mapping peer UUIDs to last-seen timestamps
        """
        now = time.time()
        with self._peers_lock:
            # Return only peers seen within timeout
            return {
                uuid: last_seen
                for uuid, last_seen in self._peers.items()
                if now - last_seen < PEER_TIMEOUT
            }

    def get_active_peer_count(self) -> int:
        """Get the number of currently active peers."""
        return len(self.get_peers())

    def _listen_loop(self) -> None:
        """Background thread: listen for incoming messages."""
        while self._running:
            try:
                data, addr = receive_multicast(self._receiver_socket)
                message = decode(data)
                self._handle_message(message)
            except TimeoutError:
                # Normal timeout, continue loop
                continue
            except OSError:
                # Socket closed during shutdown
                if self._running:
                    raise
                break
            except Exception as e:
                # Log error but keep running
                print(f"Error receiving message: {e}")
                continue

    def _heartbeat_loop(self) -> None:
        """Background thread: send periodic heartbeats."""
        while self._running:
            time.sleep(HEARTBEAT_INTERVAL)
            if self._running:
                self._send_heartbeat()

    def _send_heartbeat(self) -> None:
        """Send a heartbeat message."""
        if self._sender_socket:
            heartbeat = create_heartbeat(self.uuid)
            data = encode(heartbeat)
            try:
                send_multicast(self._sender_socket, data)
            except Exception:
                pass  # Ignore send errors for heartbeats

    def _handle_message(self, message: Message) -> None:
        """Process an incoming message."""
        # Update peer tracking (including ourselves for consistency)
        with self._peers_lock:
            if message.uuid != self.uuid:
                self._peers[message.uuid] = message.timestamp

        # Handle based on message type
        if message.type == MessageType.MESSAGE:
            # Skip our own messages
            if message.uuid == self.uuid:
                return
            # Call registered handlers
            for handler in self._handlers:
                try:
                    handler(message.uuid, message.payload)
                except Exception as e:
                    print(f"Error in message handler: {e}")

        elif message.type == MessageType.HEARTBEAT:
            # Heartbeats just update peer tracking (already done above)
            pass

    def __enter__(self) -> "AgentMessenger":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()
