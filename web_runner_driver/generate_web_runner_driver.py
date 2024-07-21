from je_web_runner import start_web_runner_socket_server

server = start_web_runner_socket_server()
while True:
    if server.close_flag:
        break
