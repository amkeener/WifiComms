"""Cross-platform UDP multicast networking."""

import socket
import struct
import sys
from typing import Tuple, Optional

# Multicast configuration
MULTICAST_GROUP = "239.255.42.1"
MULTICAST_PORT = 5007
MULTICAST_TTL = 1  # Stay on local network
BUFFER_SIZE = 65535


def create_receiver_socket(timeout: Optional[float] = None) -> socket.socket:
    """
    Create a socket for receiving multicast messages.

    Args:
        timeout: Socket timeout in seconds (None for blocking)

    Returns:
        Configured multicast receiver socket
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Allow multiple processes to bind to the same port
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # macOS requires SO_REUSEPORT for multiple listeners
    if sys.platform == "darwin":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

    # Bind to the multicast port
    # On Linux, bind to the multicast group; on macOS, bind to INADDR_ANY
    if sys.platform == "darwin":
        sock.bind(("", MULTICAST_PORT))
    else:
        sock.bind((MULTICAST_GROUP, MULTICAST_PORT))

    # Join the multicast group
    mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    if timeout is not None:
        sock.settimeout(timeout)

    return sock


def create_sender_socket() -> socket.socket:
    """
    Create a socket for sending multicast messages.

    Returns:
        Configured multicast sender socket
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

    # Set TTL for multicast packets
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)

    # Enable loopback so sender can receive its own messages (useful for testing)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

    return sock


def send_multicast(sock: socket.socket, data: bytes) -> None:
    """
    Send data to the multicast group.

    Args:
        sock: Sender socket created by create_sender_socket()
        data: Bytes to send
    """
    sock.sendto(data, (MULTICAST_GROUP, MULTICAST_PORT))


def receive_multicast(sock: socket.socket) -> Tuple[bytes, Tuple[str, int]]:
    """
    Receive data from the multicast group.

    Args:
        sock: Receiver socket created by create_receiver_socket()

    Returns:
        Tuple of (data, (sender_ip, sender_port))

    Raises:
        socket.timeout: If socket has timeout set and no data received
    """
    data, addr = sock.recvfrom(BUFFER_SIZE)
    return data, addr
