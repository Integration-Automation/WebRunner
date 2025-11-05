import json
import socketserver
import sys
import threading

from je_web_runner.utils.executor.action_executor import execute_action


class TCPServerHandler(socketserver.BaseRequestHandler):
    """
    TCP 伺服器的請求處理器
    Request handler for TCP server
    """

    def handle(self):
        # 接收客戶端傳來的資料 (最大 8192 bytes)
        # Receive data from client (max 8192 bytes)
        command_string = str(self.request.recv(8192).strip(), encoding="utf-8")
        socket = self.request
        print("command is: " + command_string, flush=True)

        # 若收到 quit_server 指令，則關閉伺服器
        # If received "quit_server", shutdown the server
        if command_string == "quit_server":
            self.server.shutdown()
            self.server.close_flag = True
            print("Now quit server", flush=True)
        else:
            try:
                # 嘗試將字串解析為 JSON
                # Try to parse string as JSON
                execute_str = json.loads(command_string)

                # 執行動作並逐一回傳結果
                # Execute actions and return results one by one
                for execute_function, execute_return in execute_action(execute_str).items():
                    socket.sendto(str(execute_return).encode("utf-8"), self.client_address)
                    socket.sendto("\n".encode("utf-8"), self.client_address)

                # 傳送結束標記
                # Send end marker
                socket.sendto("Return_Data_Over_JE".encode("utf-8"), self.client_address)
                socket.sendto("\n".encode("utf-8"), self.client_address)

            except Exception as error:
                # 若執行過程出錯，將錯誤訊息回傳給客戶端
                # If execution fails, send error message back to client
                try:
                    socket.sendto(str(error).encode("utf-8"), self.client_address)
                    socket.sendto("\n".encode("utf-8"), self.client_address)
                    socket.sendto("Return_Data_Over_JE".encode("utf-8"), self.client_address)
                    socket.sendto("\n".encode("utf-8"), self.client_address)
                except Exception as error:
                    print(repr(error))


class TCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """
    支援多執行緒的 TCP 伺服器
    Multi-threaded TCP server
    """

    def __init__(self, server_address, request_handler_class):
        super().__init__(server_address, request_handler_class)
        self.close_flag: bool = False


def start_web_runner_socket_server(host: str = "localhost", port: int = 9941):
    """
    啟動 WebRunner TCP Socket Server
    Start WebRunner TCP Socket Server

    :param host: 伺服器主機 (預設 localhost) / server host (default: localhost)
    :param port: 伺服器埠號 (預設 9941) / server port (default: 9941)
    :return: TCPServer instance
    """
    # 支援從命令列參數覆寫 host 與 port
    # Support overriding host and port from command line args
    if len(sys.argv) == 2:
        host = sys.argv[1]
    elif len(sys.argv) == 3:
        host = sys.argv[1]
        port = int(sys.argv[2])

    server = TCPServer((host, port), TCPServerHandler)

    # 使用背景執行緒啟動伺服器
    # Start server in background thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    return server