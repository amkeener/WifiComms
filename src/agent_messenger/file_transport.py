"""File-based IPC transport for Docker/cross-network communication."""

import json
import os
import time
import glob
import threading
from pathlib import Path
from typing import Callable, Optional, Dict, List

from .protocol import Message, MessageType, encode, decode

# File transport settings
FILE_POLL_INTERVAL = 0.5  # seconds between polls
MESSAGE_TTL = 60.0  # seconds before messages are cleaned up
CLEANUP_INTERVAL = 30.0  # seconds between cleanup runs


class FileTransport:
    """
    File-based message transport for environments where multicast doesn't work.

    Messages are written as JSON files to a shared directory. Each agent
    polls the directory for new messages from other agents.

    Directory structure:
        {base_dir}/
            messages/
                {uuid}_{timestamp}_{seq}.json  # Message files
            heartbeats/
                {uuid}.json  # Heartbeat files (overwritten)
    """

    def __init__(self, base_dir: str, uuid: str):
        """
        Initialize file transport.

        Args:
            base_dir: Shared directory path accessible by all agents
            uuid: This agent's UUID
        """
        self.base_dir = Path(base_dir)
        self.uuid = uuid
        self._seq = 0
        self._seq_lock = threading.Lock()
        self._seen_messages: Dict[str, float] = {}  # filename -> timestamp seen
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._cleanup_thread: Optional[threading.Thread] = None
        self._handlers: List[Callable[[Message], None]] = []

        # Create directories
        self.messages_dir = self.base_dir / "messages"
        self.heartbeats_dir = self.base_dir / "heartbeats"
        self.messages_dir.mkdir(parents=True, exist_ok=True)
        self.heartbeats_dir.mkdir(parents=True, exist_ok=True)

    def add_handler(self, handler: Callable[[Message], None]) -> None:
        """Register a message handler."""
        self._handlers.append(handler)

    def start(self) -> None:
        """Start the file transport (polling and cleanup threads)."""
        if self._running:
            return

        self._running = True

        # Start poll thread
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name=f"FileTransport-Poll-{self.uuid[:8]}",
        )
        self._poll_thread.start()

        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name=f"FileTransport-Cleanup-{self.uuid[:8]}",
        )
        self._cleanup_thread.start()

    def stop(self) -> None:
        """Stop the file transport."""
        self._running = False

        if self._poll_thread:
            self._poll_thread.join(timeout=2.0)
            self._poll_thread = None

        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=2.0)
            self._cleanup_thread = None

    def send(self, message: Message) -> None:
        """
        Send a message by writing to file.

        Args:
            message: Message to send
        """
        with self._seq_lock:
            self._seq += 1
            seq = self._seq

        filename = f"{message.uuid}_{int(message.timestamp * 1000)}_{seq}.json"
        filepath = self.messages_dir / filename

        try:
            data = encode(message).decode("utf-8")
            # Write atomically using temp file + rename
            temp_path = filepath.with_suffix(".tmp")
            temp_path.write_text(data)
            temp_path.rename(filepath)
        except Exception as e:
            print(f"Error writing message file: {e}")

    def send_heartbeat(self, message: Message) -> None:
        """
        Send a heartbeat by writing/overwriting heartbeat file.

        Args:
            message: Heartbeat message
        """
        filepath = self.heartbeats_dir / f"{message.uuid}.json"

        try:
            data = encode(message).decode("utf-8")
            temp_path = filepath.with_suffix(".tmp")
            temp_path.write_text(data)
            temp_path.rename(filepath)
        except Exception:
            pass  # Ignore heartbeat errors

    def get_peers(self) -> Dict[str, float]:
        """
        Get active peers from heartbeat files.

        Returns:
            Dict mapping peer UUIDs to last-seen timestamps
        """
        peers = {}
        now = time.time()

        try:
            for filepath in self.heartbeats_dir.glob("*.json"):
                try:
                    data = filepath.read_text()
                    message = decode(data.encode("utf-8"))
                    # Only include recent heartbeats and exclude self
                    if message.uuid != self.uuid and now - message.timestamp < MESSAGE_TTL:
                        peers[message.uuid] = message.timestamp
                except Exception:
                    continue
        except Exception:
            pass

        return peers

    def _poll_loop(self) -> None:
        """Background thread: poll for new messages."""
        while self._running:
            try:
                self._poll_messages()
            except Exception as e:
                print(f"Error polling messages: {e}")

            time.sleep(FILE_POLL_INTERVAL)

    def _poll_messages(self) -> None:
        """Check for new message files."""
        try:
            for filepath in sorted(self.messages_dir.glob("*.json")):
                filename = filepath.name

                # Skip already seen messages
                if filename in self._seen_messages:
                    continue

                # Skip our own messages (filename starts with our uuid)
                if filename.startswith(self.uuid):
                    self._seen_messages[filename] = time.time()
                    continue

                try:
                    data = filepath.read_text()
                    message = decode(data.encode("utf-8"))

                    # Mark as seen
                    self._seen_messages[filename] = time.time()

                    # Call handlers
                    for handler in self._handlers:
                        try:
                            handler(message)
                        except Exception as e:
                            print(f"Error in file transport handler: {e}")

                except Exception as e:
                    # Mark as seen even on error to avoid retrying
                    self._seen_messages[filename] = time.time()
                    print(f"Error reading message {filename}: {e}")

        except Exception:
            pass

    def _cleanup_loop(self) -> None:
        """Background thread: clean up old messages."""
        while self._running:
            time.sleep(CLEANUP_INTERVAL)
            if self._running:
                self._cleanup_old_messages()

    def _cleanup_old_messages(self) -> None:
        """Remove old message files and seen tracking."""
        now = time.time()

        # Clean up old message files (only our own)
        try:
            for filepath in self.messages_dir.glob(f"{self.uuid}_*.json"):
                try:
                    mtime = filepath.stat().st_mtime
                    if now - mtime > MESSAGE_TTL:
                        filepath.unlink()
                except Exception:
                    pass
        except Exception:
            pass

        # Clean up seen messages tracking
        old_keys = [
            k for k, v in self._seen_messages.items()
            if now - v > MESSAGE_TTL * 2
        ]
        for k in old_keys:
            del self._seen_messages[k]

        # Clean up our heartbeat if we're stopping
        if not self._running:
            try:
                (self.heartbeats_dir / f"{self.uuid}.json").unlink(missing_ok=True)
            except Exception:
                pass

    def __enter__(self) -> "FileTransport":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()
