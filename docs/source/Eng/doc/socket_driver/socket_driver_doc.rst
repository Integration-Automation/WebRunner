Remote Automation (Socket Server)
=================================

Overview
--------

WebRunner includes a multi-threaded TCP socket server for remote automation control.
This enables cross-language support -- any language that supports TCP sockets
(Java, C#, Go, etc.) can send automation commands to WebRunner.

Starting the Server
-------------------

.. code-block:: python

    from je_web_runner import start_web_runner_socket_server

    server = start_web_runner_socket_server(host="localhost", port=9941)

The server starts in a background daemon thread and is ready to accept connections immediately.

You can also override the host and port via command-line arguments:

.. code-block:: bash

    python your_script.py localhost 9941

Client Connection Example
-------------------------

.. code-block:: python

    import socket
    import json

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", 9941))

    # Send actions as JSON (UTF-8 encoded)
    actions = [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://example.com"}],
        ["WR_quit"]
    ]
    sock.send(json.dumps(actions).encode("utf-8"))

    # Receive results (ends with "Return_Data_Over_JE\n")
    response = sock.recv(4096).decode("utf-8")
    print(response)

    # Shutdown server
    sock.send("quit_server".encode("utf-8"))

Protocol
--------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Property
     - Value
   * - Default host
     - ``localhost``
   * - Default port
     - ``9941``
   * - Encoding
     - UTF-8
   * - Message format
     - JSON array of actions
   * - Max receive buffer
     - 8192 bytes
   * - Response terminator
     - ``Return_Data_Over_JE``
   * - Shutdown command
     - ``quit_server``
   * - Threading model
     - Multi-threaded (``socketserver.ThreadingMixIn``)

Response Format
---------------

After executing actions, the server sends results back one by one.
Each result is followed by a newline (``\n``).
The final message is always ``Return_Data_Over_JE\n``.

If an error occurs, the error message is sent to the client followed by the same terminator.

Server Classes
--------------

**TCPServerHandler** (extends ``socketserver.BaseRequestHandler``):
Handles incoming requests, parses JSON, executes actions, and returns results.

**TCPServer** (extends ``socketserver.ThreadingMixIn, socketserver.TCPServer``):
Multi-threaded TCP server with a ``close_flag`` attribute for shutdown control.
