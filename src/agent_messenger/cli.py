"""Command-line interface for agent-messenger."""

import argparse
import signal
import sys
import time
from datetime import datetime

from .messenger import AgentMessenger
from .protocol import generate_uuid


def format_timestamp(ts: float) -> str:
    """Format a timestamp for display."""
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def cmd_send(args: argparse.Namespace) -> None:
    """Send a message and exit."""
    messenger = AgentMessenger(uuid=args.uuid, file_dir=args.file_dir)
    messenger.start()
    time.sleep(0.1)  # Brief delay to ensure socket is ready
    messenger.send(args.message)
    time.sleep(0.1)  # Brief delay to ensure message is sent
    messenger.stop()
    print(f"Sent: {args.message}")


def cmd_listen(args: argparse.Namespace) -> None:
    """Listen for messages until Ctrl+C."""
    messenger = AgentMessenger(uuid=args.uuid, file_dir=args.file_dir)

    @messenger.on_message
    def handle(uuid: str, text: str):
        timestamp = format_timestamp(time.time())
        print(f"[{timestamp}] {uuid[:8]}: {text}")

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\nStopping...")
        messenger.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    messenger.start()
    print(f"Listening as {messenger.uuid[:8]}... (Ctrl+C to stop)")

    # Keep main thread alive
    while True:
        time.sleep(1)


def cmd_peers(args: argparse.Namespace) -> None:
    """List active peers on the network."""
    messenger = AgentMessenger(uuid=args.uuid, file_dir=args.file_dir)
    messenger.start()

    # Wait to discover peers
    print(f"Discovering peers for {args.wait} seconds...")
    time.sleep(args.wait)

    peers = messenger.get_peers()
    messenger.stop()

    if not peers:
        print("No peers found.")
        return

    print(f"\nFound {len(peers)} peer(s):")
    now = time.time()
    for uuid, last_seen in sorted(peers.items(), key=lambda x: x[1], reverse=True):
        ago = now - last_seen
        print(f"  {uuid}  (seen {ago:.1f}s ago)")


def cmd_interactive(args: argparse.Namespace) -> None:
    """Interactive REPL mode."""
    messenger = AgentMessenger(uuid=args.uuid, file_dir=args.file_dir)

    @messenger.on_message
    def handle(uuid: str, text: str):
        timestamp = format_timestamp(time.time())
        # Print on new line and reshow prompt
        print(f"\r[{timestamp}] {uuid[:8]}: {text}")
        print("> ", end="", flush=True)

    messenger.start()
    print(f"Interactive mode as {messenger.uuid[:8]}")
    print("Commands: /peers, /quit")
    print("Type a message and press Enter to send.\n")

    try:
        while True:
            try:
                line = input("> ")
            except EOFError:
                break

            line = line.strip()
            if not line:
                continue

            if line == "/quit":
                break
            elif line == "/peers":
                peers = messenger.get_peers()
                if peers:
                    print(f"Active peers ({len(peers)}):")
                    now = time.time()
                    for uuid, last_seen in peers.items():
                        print(f"  {uuid[:8]} (seen {now - last_seen:.1f}s ago)")
                else:
                    print("No peers found.")
            elif line.startswith("/"):
                print(f"Unknown command: {line}")
            else:
                messenger.send(line)

    except KeyboardInterrupt:
        pass

    print("\nStopping...")
    messenger.stop()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="agent-messenger",
        description="UDP multicast messaging for Claude agents",
    )
    parser.add_argument(
        "--uuid",
        help="Agent UUID (auto-generated if not provided)",
        default=None,
    )
    parser.add_argument(
        "--file-dir",
        help="Directory for file-based IPC (for Docker/cross-network)",
        default=None,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # send command
    send_parser = subparsers.add_parser("send", help="Send a message and exit")
    send_parser.add_argument("message", help="Message to send")

    # listen command
    listen_parser = subparsers.add_parser("listen", help="Listen for messages")

    # peers command
    peers_parser = subparsers.add_parser("peers", help="List active peers")
    peers_parser.add_argument(
        "--wait",
        type=float,
        default=3.0,
        help="Seconds to wait for peer discovery (default: 3)",
    )

    # interactive command
    interactive_parser = subparsers.add_parser(
        "interactive", help="Interactive REPL mode"
    )

    args = parser.parse_args()

    if args.command == "send":
        cmd_send(args)
    elif args.command == "listen":
        cmd_listen(args)
    elif args.command == "peers":
        cmd_peers(args)
    elif args.command == "interactive":
        cmd_interactive(args)


if __name__ == "__main__":
    main()
