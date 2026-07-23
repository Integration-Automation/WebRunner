import codecs
import json
import socketserver
import ssl
import sys
import threading
from secrets import compare_digest

from je_web_runner.utils.executor.action_executor import execute_action

_END_MARKER = b"Return_Data_Over_JE\n"
_NEWLINE = b"\n"
_QUIT_COMMAND = "quit_server"
_RECV_BYTES = 8192
# A connected client that never sends anything would otherwise pin its
# handler thread forever; ThreadingMixIn spawns one thread per connection,
# so a handful of idle sockets could exhaust the server.
_RECV_TIMEOUT_SECONDS = 30.0
# Upper bound on a single request so a peer streaming endlessly cannot grow
# the handler's buffer without limit.
_MAX_REQUEST_BYTES = 8 * 1024 * 1024

# ---------------------------------------------------------------------------
# 長度前綴框架 / Length-prefixed framing
#
# 舊協定沒有長度資訊,伺服器只能用括號平衡「猜」訊息是否收完,而且 token 那一行
# 若跨越封包邊界就無法可靠切出。加上長度前綴後這兩個問題都消失。
#
# The legacy protocol carries no length, so the server has to *infer* where a
# message ends from bracket balance, and a token line split across packet
# boundaries cannot be separated reliably. A length prefix removes both
# problems:
#
#     WRLEN <decimal byte count>\n<body>
#
# ``body`` is byte-for-byte what the legacy protocol sent (optional
# ``token\n`` line, then the JSON command), so framing is purely a transport
# concern layered *under* auth and parsing.
#
# Framing is auto-detected, never required: a request that does not open with
# the marker is served exactly as before, so existing clients keep working.
# Replies mirror the request's dialect — a framed request gets a framed reply,
# a legacy request keeps the ``Return_Data_Over_JE`` sentinel.
# ---------------------------------------------------------------------------
_LENGTH_PREFIX = b"WRLEN "
# marker + decimal digits + newline; anything longer is not a valid header.
_MAX_HEADER_BYTES = len(_LENGTH_PREFIX) + 24

_MODE_FRAMED = "framed"
_MODE_LEGACY = "legacy"
_MODE_UNDECIDED = "undecided"


def _detect_mode(buffer: bytes) -> str:
    """
    從已收到的位元組判斷這是不是長度前綴請求。
    Decide whether ``buffer`` opens a framed request.

    Returns ``_MODE_UNDECIDED`` while the bytes so far are still a proper
    prefix of the marker (a tiny first ``recv`` must not be misread as
    legacy). Any other divergence settles it immediately, which keeps the
    legacy rejection path as prompt as it has always been.
    """
    if buffer.startswith(_LENGTH_PREFIX):
        return _MODE_FRAMED
    if _LENGTH_PREFIX.startswith(buffer):
        return _MODE_UNDECIDED
    return _MODE_LEGACY


def encode_frame(body: bytes) -> bytes:
    """
    將 ``body`` 包成長度前綴訊框。
    Wrap ``body`` in a length-prefixed frame.

    :param body: 要傳送的原始位元組 / raw bytes to send
    :return: 可直接寫入 socket 的訊框 / a frame ready to write to the socket
    """
    if not isinstance(body, (bytes, bytearray)):
        raise TypeError("body must be bytes")
    return _LENGTH_PREFIX + str(len(body)).encode("ascii") + _NEWLINE + bytes(body)


def _split_token(payload: bytes) -> tuple[str | None, bytes]:
    """Split off the first line as a token; returns (token, remainder)."""
    parts = payload.split(b"\n", 1)
    if len(parts) != 2:
        return None, payload
    return parts[0].decode("utf-8", errors="replace"), parts[1]


class _RequestFrameScanner:
    """
    以遞增方式判斷請求是否已收完(用來決定還要不要繼續讀 socket)。
    Incremental stop condition for reading one request off the stream.

    The wire protocol carries no length prefix, so the handler cannot know
    how many ``recv`` calls a single request spans. Bracket/brace balance is
    a reliable signal: an unbalanced document is still in flight, a balanced
    one is finished (even if it later fails to parse — in that case the
    caller should reply with an error rather than block waiting for bytes
    that will never arrive).

    Each byte is scanned exactly once. Feeding the whole buffer on every
    ``recv`` instead would be quadratic in the request size. Decoding is
    incremental too, so a multi-byte character split across a chunk boundary
    is not mangled into a spurious delimiter.
    """

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._depth = 0
        self._in_string = False
        self._escaped = False
        self._saw_content = False
        self._unbalanced_close = False

    def feed(self, chunk: bytes) -> None:
        for char in self._decoder.decode(chunk):
            self._consume(char)

    def _consume(self, char: str) -> None:
        if self._in_string:
            if self._escaped:
                self._escaped = False
            elif char == "\\":
                self._escaped = True
            elif char == '"':
                self._in_string = False
            return
        if char == '"':
            self._in_string = True
            self._saw_content = True
        elif char in "[{":
            self._depth += 1
            self._saw_content = True
        elif char in "]}":
            self._depth -= 1
            if self._depth < 0:
                # More closers than openers: malformed, not truncated.
                self._unbalanced_close = True
        elif not char.isspace():
            self._saw_content = True

    @property
    def is_complete(self) -> bool:
        if self._unbalanced_close:
            return True
        if self._in_string:
            return False
        return self._saw_content and self._depth == 0


def _send_chunks(send, address, *chunks: bytes) -> None:
    """Send several byte chunks to a UDP-style endpoint, each with a trailing newline."""
    for chunk in chunks:
        send(chunk, address)
        send(_NEWLINE, address)


class TCPServerHandler(socketserver.BaseRequestHandler):
    """
    TCP 伺服器的請求處理器
    Request handler for TCP server
    """

    # Set per request in ``handle``; declared here so the attribute always
    # exists even if a subclass reaches a reply path early.
    _framed = False

    def _reply(self, *chunks: bytes) -> None:
        """
        以請求所用的格式回覆(長度前綴或舊的結束標記)。
        Reply in whichever dialect the request arrived in: one length-prefixed
        frame for framed clients, newline-separated chunks terminated by
        ``Return_Data_Over_JE`` for legacy ones.
        """
        try:
            if self._framed:
                self.request.sendall(encode_frame(_NEWLINE.join(chunks)))
                return
            _send_chunks(self.request.sendto, self.client_address, *chunks)
            self.request.sendto(_END_MARKER, self.client_address)
        except OSError as send_error:
            print(repr(send_error))

    def _authorize(self, payload: bytes) -> bytes | None:
        """Return the authenticated payload, or None to reject the request."""
        expected = getattr(self.server, "auth_token", None)
        if not expected:
            return payload
        token, remainder = _split_token(payload)
        if token is None or not compare_digest(token, expected):
            self._reply(b"unauthorized")
            return None
        return remainder.strip()

    def _handle_quit(self) -> None:
        # A framed client blocks reading its reply frame, so acknowledge
        # before tearing the server down. Legacy clients never got a reply
        # here, so that path stays byte-identical.
        if self._framed:
            self._reply(b"quit_server")
        self.server.shutdown()
        self.server.close_flag = True
        # Wake any waiter blocked on ``close_event.wait(timeout=...)``.
        self.server.close_event.set()
        print("Now quit server", flush=True)

    def _execute_and_reply(self, command_string: str) -> None:
        try:
            execute_str = json.loads(command_string)
            returns = [
                str(execute_return).encode("utf-8")
                for execute_return in execute_action(execute_str).values()
            ]
        except (ValueError, TypeError, OSError) as error:
            # JSONDecodeError inherits from ValueError, so it is already
            # covered above (SonarCloud S5713).
            self._reply(str(error).encode("utf-8"))
            return
        self._reply(*returns)

    def _recv_chunk(self) -> bytes | None:
        """One bounded ``recv``; ``None`` signals the socket is unusable."""
        try:
            return self.request.recv(_RECV_BYTES)
        except OSError as error:
            # Covers socket.timeout (an OSError subclass) and peers that
            # reset the connection before sending a full request.
            print(f"socket receive failed: {error!r}", flush=True)
            return None

    def _fill_until(self, buffer: bytearray, predicate, limit: int) -> bool:
        """Keep reading into ``buffer`` until ``predicate`` holds or ``limit`` trips."""
        while not predicate(buffer):
            if len(buffer) > limit:
                print(f"request exceeded {limit} bytes; dropping", flush=True)
                return False
            chunk = self._recv_chunk()
            if not chunk:
                return False
            buffer.extend(chunk)
        return True

    def _read_framed_body(self, buffer: bytearray) -> bytes | None:
        """
        讀取 ``WRLEN <n>\\n`` 標頭並收滿 n 個位元組。
        Read the ``WRLEN <n>\\n`` header, then exactly ``n`` bytes of body.

        With an explicit length there is no guessing: the body is complete
        when the byte count is met, so a token line spanning packet
        boundaries is no longer a problem.
        """
        if not self._fill_until(buffer, lambda buf: _NEWLINE in buf, _MAX_HEADER_BYTES):
            return None
        header, _, rest = bytes(buffer).partition(_NEWLINE)
        try:
            declared = int(header[len(_LENGTH_PREFIX):].strip())
        except ValueError:
            print(f"malformed length header: {header!r}", flush=True)
            return None
        if declared < 0 or declared > _MAX_REQUEST_BYTES:
            print(f"declared length out of range: {declared}", flush=True)
            return None
        body = bytearray(rest)
        if not self._fill_until(body, lambda buf: len(buf) >= declared, _MAX_REQUEST_BYTES):
            # Peer stopped early: an under-length body is a truncated
            # request, not something to hand to the executor.
            print(
                f"framed body truncated: got {len(body)} of {declared} bytes",
                flush=True,
            )
            return None
        return bytes(body[:declared])

    def _read_legacy_body(self, buffer: bytearray) -> bytes | None:
        """
        舊協定:先在第一段做驗證,再靠括號平衡判斷何時收完。
        Legacy path: authorise on the first segment, then use bracket balance
        to decide when the body has fully arrived.

        Authorisation cannot wait for a complete body here — a client sending
        a bad or absent token must be rejected immediately rather than kept
        waiting for bytes it is never going to send.
        """
        payload = self._authorize(bytes(buffer).strip())
        if payload is None:
            return None
        scanner = _RequestFrameScanner()
        scanner.feed(payload)
        body = bytearray(payload)
        # Not ``_fill_until``: the scanner has to be fed every chunk, so the
        # loop advances both the buffer and the stop condition together.
        while not scanner.is_complete:
            if len(body) > _MAX_REQUEST_BYTES:
                print(f"request exceeded {_MAX_REQUEST_BYTES} bytes; dropping", flush=True)
                return None
            chunk = self._recv_chunk()
            if not chunk:
                # A peer that closes early still gets its reply: whatever
                # arrived is handed on so a parse error comes back rather
                # than silence.
                break
            body.extend(chunk)
            scanner.feed(chunk)
        return bytes(body)

    def _receive_request(self) -> bytes | None:
        """
        讀滿一個完整請求,自動辨識長度前綴或舊格式。
        Read one whole request, auto-detecting framed vs legacy format.
        """
        self.request.settimeout(_RECV_TIMEOUT_SECONDS)
        buffer = bytearray()
        mode = _MODE_UNDECIDED
        while mode == _MODE_UNDECIDED:
            chunk = self._recv_chunk()
            if not chunk:
                return None
            buffer.extend(chunk)
            mode = _detect_mode(bytes(buffer))
        if mode == _MODE_FRAMED:
            self._framed = True
            body = self._read_framed_body(buffer)
            # The frame is transport only; auth still applies to its contents,
            # and now sees the whole body at once.
            return None if body is None else self._authorize(body.strip())
        return self._read_legacy_body(buffer)

    def handle(self):
        self._framed = False
        raw = self._receive_request()
        if raw is None:
            return
        command_string = raw.decode("utf-8", errors="replace").strip()
        print("command is: " + command_string, flush=True)
        if command_string == _QUIT_COMMAND:
            self._handle_quit()
        else:
            self._execute_and_reply(command_string)


class TCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """
    支援多執行緒的 TCP 伺服器，可選 token 驗證與 TLS
    Multi-threaded TCP server with optional token auth and TLS.
    """

    def __init__(self, server_address, request_handler_class, auth_token: str | None = None):
        super().__init__(server_address, request_handler_class)
        self.close_flag: bool = False
        # ``close_event`` lets callers wait for shutdown without polling.
        self.close_event: threading.Event = threading.Event()
        self.auth_token: str | None = auth_token


def _read_exactly(sock, count: int) -> bytes:
    """Read exactly ``count`` bytes or raise on a short stream."""
    buffer = bytearray()
    while len(buffer) < count:
        chunk = sock.recv(min(_RECV_BYTES, count - len(buffer)))
        if not chunk:
            raise ConnectionError(
                f"connection closed after {len(buffer)} of {count} bytes"
            )
        buffer.extend(chunk)
    return bytes(buffer)


def read_frame(sock) -> bytes:
    """
    從 ``sock`` 讀取一個長度前綴訊框並回傳其內容。
    Read one length-prefixed frame from ``sock`` and return its body.

    :param sock: 已連線的 socket / a connected socket
    :return: 訊框內容 / the frame body
    """
    header = bytearray()
    while not header.endswith(_NEWLINE):
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("connection closed while reading frame header")
        header.extend(chunk)
        if len(header) > _MAX_HEADER_BYTES:
            raise ValueError(f"frame header too long: {bytes(header)!r}")
    if not header.startswith(_LENGTH_PREFIX):
        raise ValueError(f"not a length-prefixed frame: {bytes(header)!r}")
    declared = int(bytes(header)[len(_LENGTH_PREFIX):].strip())
    return _read_exactly(sock, declared)


def send_command(
    sock,
    command: str | bytes,
    auth_token: str | None = None,
) -> bytes:
    """
    以長度前綴格式送出一筆指令並讀回回覆。
    Send one command using length-prefixed framing and return the reply body.

    Framing removes the guesswork of the legacy protocol: neither side has to
    infer where a message ends, so oversized payloads and a token line landing
    on a packet boundary are both handled correctly.

    :param sock: 已連線到 WebRunner socket server 的 socket
                 A socket already connected to the WebRunner socket server
    :param command: 動作 JSON 字串或 ``quit_server``
                    Action JSON string, or ``quit_server``
    :param auth_token: 伺服器啟用 token 驗證時必填 / required when the server
                       was started with ``auth_token``
    :return: 伺服器回覆內容 / the server's reply body
    """
    body = command.encode("utf-8") if isinstance(command, str) else bytes(command)
    if auth_token is not None:
        body = auth_token.encode("utf-8") + _NEWLINE + body
    sock.sendall(encode_frame(body))
    return read_frame(sock)


def _build_tls_context(certfile: str, keyfile: str) -> ssl.SSLContext:
    # ``Purpose.CLIENT_AUTH`` only sets the side; explicitly pin TLSv1.2+
    # so SonarCloud S4423 is satisfied even on older Pythons that may
    # leave the default minimum at TLSv1.0.
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certfile=certfile, keyfile=keyfile)
    return context


def _resolve_argv_overrides(host: str, port: int) -> tuple[str, int]:
    """Honour positional CLI overrides if argv looks like a host/port pair."""
    if len(sys.argv) == 2:
        return sys.argv[1], port
    if len(sys.argv) == 3:
        return sys.argv[1], int(sys.argv[2])
    return host, port


def start_web_runner_socket_server(
    host: str = "localhost",
    port: int = 9941,
    auth_token: str | None = None,
    certfile: str | None = None,
    keyfile: str | None = None,
):
    """
    啟動 WebRunner TCP Socket Server，可選 token 驗證與 TLS
    Start the WebRunner TCP Socket Server with optional token auth and TLS.

    :param host: 預設為 localhost；對外暴露時請明確指定
                 Defaults to localhost; specify explicitly when exposing externally.
    :param port: 監聽埠號 / listen port
    :param auth_token: 若提供，每筆訊息第一行需為 token
                       If set, every message must begin with the token followed by ``\\n``.
    :param certfile: TLS 憑證檔路徑 / TLS certificate path (PEM)
    :param keyfile: TLS 私鑰檔路徑 / TLS private key path (PEM)
    :return: TCPServer 實例 / TCPServer instance
    """
    host, port = _resolve_argv_overrides(host, port)
    server = TCPServer((host, port), TCPServerHandler, auth_token=auth_token)
    if certfile and keyfile:
        context = _build_tls_context(certfile, keyfile)
        server.socket = context.wrap_socket(server.socket, server_side=True)

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    return server
