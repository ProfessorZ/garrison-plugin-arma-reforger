"""
Async UDP BattlEye RCON client for Arma Reforger.

Implements the BattlEye RCON v2 protocol over UDP with CRC32 packet
verification, multi-packet reassembly, automatic keepalives, and
server-message acknowledgement.
"""

import asyncio
import struct
import zlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Protocol constants
HEADER_PREFIX = b"\x42\x45"  # "BE"
HEADER_SUFFIX = b"\xff"
LOGIN_TYPE = 0x00
COMMAND_TYPE = 0x01
SERVER_MSG_TYPE = 0x02
KEEPALIVE_INTERVAL = 30
LOGIN_TIMEOUT = 5
COMMAND_TIMEOUT = 10


def _build_packet(payload: bytes) -> bytes:
    """Build a BattlEye RCON packet with header, CRC32, and payload."""
    crc = zlib.crc32(b"\xff" + payload) & 0xFFFFFFFF
    return HEADER_PREFIX + struct.pack("<I", crc) + HEADER_SUFFIX + payload


def _verify_packet(data: bytes) -> Optional[bytes]:
    """Verify and strip the BE header, returning the payload or None."""
    if len(data) < 7 or data[:2] != HEADER_PREFIX or data[6:7] != HEADER_SUFFIX:
        return None
    crc_received = struct.unpack("<I", data[2:6])[0]
    payload = data[7:]
    crc_computed = zlib.crc32(b"\xff" + payload) & 0xFFFFFFFF
    if crc_received != crc_computed:
        logger.warning("CRC mismatch: expected %08x, got %08x", crc_computed, crc_received)
        return None
    return payload


class BERConProtocol(asyncio.DatagramProtocol):
    """Low-level asyncio datagram protocol for BattlEye RCON."""

    def __init__(self, connection: "BERConConnection"):
        self.connection = connection
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        payload = _verify_packet(data)
        if payload is None:
            logger.debug("Dropped invalid packet from %s", addr)
            return
        self.connection._handle_payload(payload)

    def error_received(self, exc: Exception) -> None:
        logger.error("UDP error: %s", exc)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        logger.info("Connection lost: %s", exc)
        self.connection._on_connection_lost()


class BERConConnection:
    """Async BattlEye RCON connection for Arma Reforger.

    Usage::

        conn = BERConConnection("127.0.0.1", 2301, "mypassword")
        await conn.connect()
        response = await conn.send_command("get players")
        await conn.close()
    """

    def __init__(self, host: str, port: int, password: str):
        self.host = host
        self.port = port
        self.password = password

        self._transport: Optional[asyncio.DatagramTransport] = None
        self._protocol: Optional[BERConProtocol] = None
        self._seq: int = 0
        self._logged_in = False

        # Login state
        self._login_event: Optional[asyncio.Event] = None
        self._login_success: bool = False

        # Pending command responses keyed by sequence number
        self._pending: dict[int, asyncio.Future] = {}

        # Multi-packet reassembly: seq -> {total, parts: {index: data}}
        self._multipacket: dict[int, dict] = {}

        # Background tasks
        self._keepalive_task: Optional[asyncio.Task] = None
        self._closed = False

        # Callback for server messages
        self.on_server_message: Optional[callable] = None

    async def connect(self) -> None:
        """Open the UDP socket and perform the login handshake."""
        loop = asyncio.get_running_loop()
        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: BERConProtocol(self),
            remote_addr=(self.host, self.port),
        )

        self._login_event = asyncio.Event()
        login_payload = bytes([LOGIN_TYPE]) + self.password.encode("ascii")
        self._transport.sendto(_build_packet(login_payload))

        try:
            await asyncio.wait_for(self._login_event.wait(), timeout=LOGIN_TIMEOUT)
        except asyncio.TimeoutError:
            self._transport.close()
            raise ConnectionError("Login timed out")

        if not self._login_success:
            self._transport.close()
            raise PermissionError("Login failed — bad RCON password")

        self._logged_in = True
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())
        logger.info("Logged in to %s:%d", self.host, self.port)

    async def send_command(self, cmd: str) -> str:
        """Send an RCON command and return the response string."""
        if not self._logged_in:
            raise RuntimeError("Not connected")

        seq = self._seq % 256
        self._seq += 1

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[seq] = future

        payload = bytes([COMMAND_TYPE, seq]) + cmd.encode("utf-8")
        self._transport.sendto(_build_packet(payload))

        try:
            result = await asyncio.wait_for(future, timeout=COMMAND_TIMEOUT)
        except asyncio.TimeoutError:
            self._pending.pop(seq, None)
            self._multipacket.pop(seq, None)
            raise TimeoutError(f"Command timed out: {cmd}")

        return result

    async def close(self) -> None:
        """Shut down the connection and cancel background tasks."""
        self._closed = True
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
        if self._transport:
            self._transport.close()
        self._logged_in = False
        logger.info("Connection closed")

    # ── internal ────────────────────────────────────────────────────

    def _handle_payload(self, payload: bytes) -> None:
        if len(payload) < 1:
            return

        ptype = payload[0]

        if ptype == LOGIN_TYPE:
            self._handle_login(payload)
        elif ptype == COMMAND_TYPE:
            self._handle_command_response(payload)
        elif ptype == SERVER_MSG_TYPE:
            self._handle_server_message(payload)
        else:
            logger.debug("Unknown packet type: 0x%02x", ptype)

    def _handle_login(self, payload: bytes) -> None:
        self._login_success = len(payload) >= 2 and payload[1] == 0x01
        if self._login_event:
            self._login_event.set()

    def _handle_command_response(self, payload: bytes) -> None:
        if len(payload) < 2:
            return

        seq = payload[1]

        # Check for multi-packet response
        if len(payload) >= 5 and payload[2] == 0x00:
            total = payload[3]
            index = payload[4]
            data = payload[5:]
            self._handle_multipacket(seq, total, index, data)
            return

        # Single-packet response
        data = payload[2:].decode("utf-8", errors="replace")
        future = self._pending.pop(seq, None)
        if future and not future.done():
            future.set_result(data)

    def _handle_multipacket(self, seq: int, total: int, index: int, data: bytes) -> None:
        if seq not in self._multipacket:
            self._multipacket[seq] = {"total": total, "parts": {}}

        entry = self._multipacket[seq]
        entry["parts"][index] = data

        if len(entry["parts"]) >= entry["total"]:
            assembled = b""
            for i in range(entry["total"]):
                assembled += entry["parts"].get(i, b"")
            del self._multipacket[seq]

            result = assembled.decode("utf-8", errors="replace")
            future = self._pending.pop(seq, None)
            if future and not future.done():
                future.set_result(result)

    def _handle_server_message(self, payload: bytes) -> None:
        if len(payload) < 2:
            return
        seq = payload[1]
        message = payload[2:].decode("utf-8", errors="replace")

        # ACK the server message
        ack = _build_packet(bytes([SERVER_MSG_TYPE, seq]))
        if self._transport:
            self._transport.sendto(ack)

        logger.debug("Server message [%d]: %s", seq, message)
        if self.on_server_message:
            self.on_server_message(message)

    def _on_connection_lost(self) -> None:
        self._logged_in = False
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionError("Connection lost"))
        self._pending.clear()

    async def _keepalive_loop(self) -> None:
        """Send an empty command packet every KEEPALIVE_INTERVAL seconds."""
        try:
            while self._logged_in and not self._closed:
                await asyncio.sleep(KEEPALIVE_INTERVAL)
                if self._logged_in and self._transport:
                    seq = self._seq % 256
                    self._seq += 1
                    payload = bytes([COMMAND_TYPE, seq])
                    self._transport.sendto(_build_packet(payload))
                    logger.debug("Keepalive sent (seq %d)", seq)
        except asyncio.CancelledError:
            pass
