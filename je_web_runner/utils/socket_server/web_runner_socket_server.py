import json
import socketserver
import ssl
import sys
import threading
from secrets import compare_digest
from typing import Optional

from je_web_runner.utils.executor.action_executor import execute_action

_END_MARKER = b"Return_Data_Over_JE\n"
_NEWLINE = b"\n"
_QUIT_COMMAND = "quit_server"
_RECV_BYTES = 8192


def _split_token(payload: bytes) -> tuple[Optional[str], bytes]:
    """Split off the first line as a token; returns (token, remainder)."""
    parts = payload.split(b"\n", 1)
    if len(parts) != 2:
        return None, payload
    return parts[0].decode("utf-8", errors="replace"), parts[1]


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

    def _authorize(self, payload: bytes) -> Optional[bytes]:
        """Return the authenticated payload, or None to reject the request."""
        expected = getattr(self.server, "auth_token", None)
        if not expected:
            return payload
        token, remainder = _split_token(payload)
        if token is None or not compare_digest(token, expected):
            self.request.sendto(b"unauthorized\n", self.client_address)
            self.request.sendto(_END_MARKER, self.client_address)
            return None
        return remainder.strip()

    def _handle_quit(self) -> None:
        self.server.shutdown()
        self.server.close_flag = True
        # Wake any waiter blocked on ``close_event.wait(timeout=...)``.
        self.server.close_event.set()
        print("Now quit server", flush=True)

    def _execute_and_reply(self, command_string: str) -> None:
        try:
            execute_str = json.loads(command_string)
            socket = self.request
            for execute_return in execute_action(execute_str).values():
                _send_chunks(socket.sendto, self.client_address, str(execute_return).encode("utf-8"))
            socket.sendto(_END_MARKER, self.client_address)
        except (ValueError, TypeError, OSError) as error:
            # JSONDecodeError inherits from ValueError, so it is already
            # covered above (SonarCloud S5713).
            try:
                socket = self.request
                _send_chunks(socket.sendto, self.client_address, str(error).encode("utf-8"))
                socket.sendto(_END_MARKER, self.client_address)
            except OSError as send_error:
                print(repr(send_error))

    def handle(self):
        raw = self.request.recv(_RECV_BYTES).strip()
        payload = self._authorize(raw)
        if payload is None:
            return
        command_string = payload.decode("utf-8", errors="replace").strip()
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

    def __init__(self, server_address, request_handler_class, auth_token: Optional[str] = None):
        super().__init__(server_address, request_handler_class)
        self.close_flag: bool = False
        # ``close_event`` lets callers wait for shutdown without polling.
        self.close_event: threading.Event = threading.Event()
        self.auth_token: Optional[str] = auth_token


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
    auth_token: Optional[str] = None,
    certfile: Optional[str] = None,
    keyfile: Optional[str] = None,
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
