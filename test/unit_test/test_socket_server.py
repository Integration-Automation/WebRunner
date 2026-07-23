import json
import socket
import threading
import unittest

from je_web_runner.utils.socket_server.web_runner_socket_server import (
    _detect_mode,
    _MODE_FRAMED,
    _MODE_LEGACY,
    _MODE_UNDECIDED,
    _RECV_BYTES,
    _RequestFrameScanner,
    encode_frame,
    read_frame,
    send_command,
    TCPServer,
    TCPServerHandler,
)


def _start_server(auth_token=None):  # nosec B106 — caller passes a fixture token
    server = TCPServer(("127.0.0.1", 0), TCPServerHandler, auth_token=auth_token)
    # Tight poll_interval so ``shutdown()`` returns quickly inside tests.
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
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
            self.assertTrue(server.close_event.wait(timeout=2.0))
            self.assertTrue(server.close_flag)
        finally:
            try:
                server.server_close()
            except OSError:
                pass

    def test_request_without_token_is_rejected(self):
        server, _ = _start_server(auth_token="secret")  # nosec B106 — fake fixture
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
        server, _ = _start_server(auth_token="secret")  # nosec B106 — fake fixture
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
        server, _ = _start_server(auth_token="secret")  # nosec B106 — fake fixture
        try:
            host, port = server.server_address
            with socket.create_connection((host, port)) as client:
                client.sendall(b"secret\nquit_server")
            self.assertTrue(server.close_event.wait(timeout=2.0))
            self.assertTrue(server.close_flag)
        finally:
            try:
                server.server_close()
            except OSError:
                pass


class TestRequestFrameScanner(unittest.TestCase):
    """The stop condition that decides whether more bytes are still coming."""

    @staticmethod
    def _scan(*chunks):
        scanner = _RequestFrameScanner()
        for chunk in chunks:
            scanner.feed(chunk)
        return scanner.is_complete

    def test_balanced_document_is_complete(self):
        self.assertTrue(self._scan(b'[["WR_quit"]]'))

    def test_bare_command_is_complete(self):
        self.assertTrue(self._scan(b"quit_server"))

    def test_truncated_document_is_incomplete(self):
        self.assertFalse(self._scan(b'[["WR_quit"'))

    def test_unterminated_string_is_incomplete(self):
        self.assertFalse(self._scan(b'[["WR_qu'))

    def test_brackets_inside_string_do_not_count(self):
        # The ']' characters are string content, not structure.
        self.assertFalse(self._scan(b'[["]]]]"'))
        self.assertTrue(self._scan(b'[["]]]]"]]'))

    def test_escaped_quote_does_not_close_string(self):
        self.assertFalse(self._scan(b'[["a\\""'))
        self.assertTrue(self._scan(b'[["a\\""]]'))

    def test_completeness_is_reached_across_chunks(self):
        self.assertTrue(self._scan(b'[["WR_', b'quit"]', b"]"))

    def test_empty_input_is_incomplete(self):
        self.assertFalse(self._scan(b"", b"   \n "))

    def test_excess_closer_stops_reading(self):
        # Malformed rather than truncated — waiting for more would just
        # stall until the timeout, so treat it as finished and let the
        # JSON parse fail into an error reply.
        self.assertTrue(self._scan(b'[["a"]]]]'))

    def test_multibyte_char_split_across_chunks(self):
        payload = '[["測試"]]'.encode("utf-8")
        # Split mid-character; the incremental decoder must not mangle it
        # into something that looks like a delimiter.
        self.assertTrue(self._scan(payload[:6], payload[6:]))


class TestLargeAndFragmentedRequests(unittest.TestCase):
    """TCP is a stream: one recv() is not one message."""

    def setUp(self):
        self.server, _ = _start_server()
        self.addCleanup(self._stop)

    def _stop(self):
        try:
            self.server.shutdown()
            self.server.server_close()
        except OSError:
            pass

    def _round_trip(self, payload: bytes, chunk_size: int | None = None) -> bytes:
        host, port = self.server.server_address
        with socket.create_connection((host, port)) as client:
            if chunk_size is None:
                client.sendall(payload)
            else:
                for start in range(0, len(payload), chunk_size):
                    client.sendall(payload[start:start + chunk_size])
            return _read_until_marker(client)

    def test_payload_larger_than_one_recv_is_not_truncated(self):
        # Comfortably more than a single _RECV_BYTES read.
        padding = "A" * (_RECV_BYTES * 6)
        payload = json.dumps([["WR_unknown_command", {"padding": padding}]]).encode()
        self.assertGreater(len(payload), _RECV_BYTES)

        reply = self._round_trip(payload)

        # Reaching the executor at all proves the whole document was parsed:
        # a truncated body would have failed in json.loads instead.
        self.assertIn(b"unknown command: WR_unknown_command", reply)

    def test_fragmented_send_is_reassembled(self):
        payload = json.dumps([["WR_unknown_command", {"padding": "B" * 20000}]]).encode()

        reply = self._round_trip(payload, chunk_size=1024)

        self.assertIn(b"unknown command: WR_unknown_command", reply)

    def test_malformed_but_balanced_json_replies_promptly(self):
        # Structure is closed, so the server must stop reading and report the
        # parse error rather than blocking until the receive timeout.
        reply = self._round_trip(b"[[[not valid json]]]")
        self.assertIn(b"Return_Data_Over_JE", reply)
        self.assertNotIn(b"unknown command", reply)


class TestFrameEncoding(unittest.TestCase):

    def test_encode_frame_layout(self):
        self.assertEqual(encode_frame(b"hello"), b"WRLEN 5\nhello")

    def test_encode_empty_body(self):
        self.assertEqual(encode_frame(b""), b"WRLEN 0\n")

    def test_length_counts_bytes_not_characters(self):
        body = "測試".encode("utf-8")  # 2 chars, 6 bytes
        self.assertEqual(encode_frame(body), b"WRLEN 6\n" + body)

    def test_non_bytes_rejected(self):
        with self.assertRaises(TypeError):
            encode_frame("not bytes")  # type: ignore[arg-type]


class TestDetectMode(unittest.TestCase):
    """Auto-detection is what keeps legacy clients working untouched."""

    def test_marker_selects_framed(self):
        self.assertEqual(_detect_mode(b"WRLEN 12\n"), _MODE_FRAMED)

    def test_json_selects_legacy(self):
        self.assertEqual(_detect_mode(b'[["WR_quit"]]'), _MODE_LEGACY)

    def test_partial_marker_is_undecided(self):
        # A tiny first recv must not be mistaken for a legacy request.
        for size in range(1, len(b"WRLEN ")):
            self.assertEqual(_detect_mode(b"WRLEN "[:size]), _MODE_UNDECIDED)

    def test_empty_is_undecided(self):
        self.assertEqual(_detect_mode(b""), _MODE_UNDECIDED)

    def test_near_miss_is_legacy(self):
        self.assertEqual(_detect_mode(b"WRLENX"), _MODE_LEGACY)
        self.assertEqual(_detect_mode(b"wrlen "), _MODE_LEGACY)


class TestFramedRequests(unittest.TestCase):

    def _serve(self, auth_token=None):
        server, _ = _start_server(auth_token=auth_token)
        self.addCleanup(self._stop, server)
        return server

    @staticmethod
    def _stop(server):
        try:
            server.shutdown()
            server.server_close()
        except OSError:
            pass

    def test_framed_round_trip(self):
        server = self._serve()
        host, port = server.server_address
        with socket.create_connection((host, port)) as client:
            reply = send_command(client, json.dumps([["WR_unknown_command"]]))
        self.assertIn(b"unknown command: WR_unknown_command", reply)

    def test_framed_payload_larger_than_one_recv(self):
        server = self._serve()
        host, port = server.server_address
        padding = "A" * (_RECV_BYTES * 6)
        command = json.dumps([["WR_unknown_command", {"padding": padding}]])
        with socket.create_connection((host, port)) as client:
            reply = send_command(client, command)
        self.assertIn(b"unknown command: WR_unknown_command", reply)

    def test_framed_token_split_across_packets_is_authorised(self):
        """The reason for the length prefix: with an explicit byte count the
        token line no longer has to arrive inside the first recv."""
        server = self._serve(auth_token="secret")  # nosec B106 — fake fixture
        host, port = server.server_address
        body = b"secret\n" + json.dumps([["WR_unknown_command"]]).encode()
        frame = encode_frame(body)
        with socket.create_connection((host, port)) as client:
            # Dribble the header and token out one byte at a time so the
            # token straddles several recv() calls.
            for index in range(14):
                client.sendall(frame[index:index + 1])
            client.sendall(frame[14:])
            reply = read_frame(client)
        self.assertIn(b"unknown command: WR_unknown_command", reply)
        self.assertNotIn(b"unauthorized", reply)

    def test_framed_wrong_token_is_rejected(self):
        server = self._serve(auth_token="secret")  # nosec B106 — fake fixture
        host, port = server.server_address
        with socket.create_connection((host, port)) as client:
            reply = send_command(  # nosec B106 — deliberately invalid fixture token
                client, json.dumps([["WR_unknown_command"]]), auth_token="wrong",
            )
        self.assertIn(b"unauthorized", reply)
        self.assertFalse(server.close_flag)

    def test_framed_quit_acknowledges_then_shuts_down(self):
        server = self._serve()
        host, port = server.server_address
        with socket.create_connection((host, port)) as client:
            reply = send_command(client, "quit_server")
        self.assertIn(b"quit_server", reply)
        self.assertTrue(server.close_event.wait(timeout=2.0))

    def test_under_length_body_is_not_executed(self):
        """A declared length the peer never delivers is a truncated request,
        so it must not be handed to the executor."""
        server = self._serve()
        host, port = server.server_address
        command = json.dumps([["WR_unknown_command"]]).encode()
        with socket.create_connection((host, port)) as client:
            # Claim more bytes than are actually sent, then close.
            client.sendall(b"WRLEN " + str(len(command) + 500).encode() + b"\n")
            client.sendall(command)
            client.shutdown(socket.SHUT_WR)
            leftover = client.recv(4096)
        self.assertEqual(leftover, b"")

    def test_malformed_length_header_is_dropped(self):
        server = self._serve()
        host, port = server.server_address
        with socket.create_connection((host, port)) as client:
            client.sendall(b"WRLEN not-a-number\n[]")
            client.shutdown(socket.SHUT_WR)
            leftover = client.recv(4096)
        self.assertEqual(leftover, b"")


class TestReadFrame(unittest.TestCase):

    def test_rejects_non_frame(self):
        server, _ = _start_server()
        self.addCleanup(TestFramedRequests._stop, server)
        host, port = server.server_address
        # The server replies to a legacy request with the sentinel format,
        # which read_frame must refuse rather than misparse.
        with socket.create_connection((host, port)) as client:
            client.sendall(json.dumps([["WR_unknown_command"]]).encode())
            with self.assertRaises(ValueError):
                read_frame(client)


if __name__ == "__main__":
    unittest.main()
