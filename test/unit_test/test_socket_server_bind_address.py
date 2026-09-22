"""The socket server binds the address it is given, whatever the host process's argv is."""
from je_web_runner import start_web_runner_socket_server


def test_command_line_arguments_do_not_rebind_the_server(monkeypatch):
    # A host program run as "prog.py some_arg" used to have "some_arg" taken as the bind host.
    monkeypatch.setattr("sys.argv", ["prog.py", "not-a-host"])
    server = start_web_runner_socket_server("127.0.0.1", 0)
    try:
        assert server.server_address[0] == "127.0.0.1"  # nosec B101
    finally:
        server.shutdown()
        server.server_close()
