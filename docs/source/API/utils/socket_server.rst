Socket Server API
=================

``je_web_runner.utils.socket_server.web_runner_socket_server``

Class: TCPServerHandler
-----------------------

.. code-block:: python

    class TCPServerHandler(socketserver.BaseRequestHandler):
        """
        Request handler for the WebRunner TCP server.

        Receives UTF-8 encoded JSON action strings (max 8192 bytes),
        executes them via execute_action(), and returns results.

        Special command: "quit_server" shuts down the server.

        Response protocol:
        - Each result is sent as UTF-8 followed by newline
        - Final message: "Return_Data_Over_JE\n"
        """

Class: TCPServer
----------------

.. code-block:: python

    class TCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        """
        Multi-threaded TCP server.

        Attributes:
            close_flag (bool): Set to True when server receives shutdown command.
        """

Function: start_web_runner_socket_server
----------------------------------------

.. code-block:: python

    def start_web_runner_socket_server(host: str = "localhost", port: int = 9941) -> TCPServer:
        """
        Start the WebRunner TCP Socket Server in a background daemon thread.

        Host and port can be overridden via sys.argv:
        - 1 arg: host
        - 2 args: host, port

        :param host: server host (default: "localhost")
        :param port: server port (default: 9941)
        :return: TCPServer instance (already serving)
        """
