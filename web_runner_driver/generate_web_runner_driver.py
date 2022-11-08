from je_web_runner import start_web_runner_socket_server

try:
    server = start_web_runner_socket_server()
    while not server.close_flag:
        pass
except Exception as error:
    print(repr(error))
