import socket
import threading
import time
import unittest

from je_web_runner.utils.socket_server.web_runner_socket_server import (
    TCPServer,
    TCPServerHandler,
)


def _start_server(auth_token=None):  # nosec B106 — caller passes a fixture token
    server = TCPServer(("127.0.0.1", 0), TCPServerHandler, auth_token=auth_token)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server, thread


def _read_until_marker(sock: socket.socket, timeout: float = 2.0) -> bytes:
    sock.settimeout(timeout)
    buffer = b""
    while b"Return_Data_Over_JE" not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buffer += chunk
    return buffer


class TestSocketServerAuth(unittest.TestCase):

    def test_quit_command_without_auth_shuts_down_server(self):
        server, _ = _start_server()
        try:
            host, port = server.server_address
            with socket.create_connection((host, port)) as client:
                client.sendall(b"quit_server")
            for _ in range(20):
                if server.close_flag:
                    break
                time.sleep(0.05)
            self.assertTrue(server.close_flag)
        finally:
            try:
                server.server_close()
            except OSError:
                pass

    def test_request_without_token_is_rejected(self):
        server, _ = _start_server(auth_token="secret")
        try:
            host, port = server.server_address
            with socket.create_connection((host, port)) as client:
                client.sendall(b'[["WR_quit"]]')
                reply = _read_until_marker(client)
            self.assertIn(b"unauthorized", reply)
            self.assertFalse(server.close_flag)
        finally:
            server.shutdown()
            server.server_close()

    def test_request_with_wrong_token_is_rejected(self):
        server, _ = _start_server(auth_token="secret")
        try:
            host, port = server.server_address
            with socket.create_connection((host, port)) as client:
                client.sendall(b"wrong\nquit_server")
                reply = _read_until_marker(client)
            self.assertIn(b"unauthorized", reply)
            self.assertFalse(server.close_flag)
        finally:
            server.shutdown()
            server.server_close()

    def test_quit_with_correct_token_shuts_down(self):
        server, _ = _start_server(auth_token="secret")
        try:
            host, port = server.server_address
            with socket.create_connection((host, port)) as client:
                client.sendall(b"secret\nquit_server")
            for _ in range(20):
                if server.close_flag:
                    break
                time.sleep(0.05)
            self.assertTrue(server.close_flag)
        finally:
            try:
                server.server_close()
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
