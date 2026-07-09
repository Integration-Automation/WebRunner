from je_web_runner import start_web_runner_socket_server

server = start_web_runner_socket_server()
# Block until the server's quit handler fires ``close_event`` instead of
# busy-waiting on ``close_flag`` (which spins a CPU core while idle).
server.close_event.wait()
