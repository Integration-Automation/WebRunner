遠端自動化（Socket 伺服器）
============================

概述
----

WebRunner 包含一個多執行緒 TCP Socket 伺服器，用於遠端自動化控制。
這使得跨語言支援成為可能 -- 任何支援 TCP Socket 的語言
（Java、C#、Go 等）都可以向 WebRunner 發送自動化指令。

啟動伺服器
----------

.. code-block:: python

    from je_web_runner import start_web_runner_socket_server

    server = start_web_runner_socket_server(host="localhost", port=9941)

伺服器在背景常駐執行緒中啟動，立即準備接受連線。

客戶端連線範例
--------------

.. code-block:: python

    import socket
    import json

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("localhost", 9941))

    # 發送 JSON 格式的動作（UTF-8 編碼）
    actions = [
        ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
        ["WR_to_url", {"url": "https://example.com"}],
        ["WR_quit"]
    ]
    sock.send(json.dumps(actions).encode("utf-8"))

    # 接收結果（以 "Return_Data_Over_JE\n" 結尾）
    response = sock.recv(4096).decode("utf-8")
    print(response)

    # 關閉伺服器
    sock.send("quit_server".encode("utf-8"))

協定
----

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - 屬性
     - 值
   * - 預設主機
     - ``localhost``
   * - 預設埠號
     - ``9941``
   * - 編碼
     - UTF-8
   * - 訊息格式
     - JSON 動作陣列
   * - 最大接收緩衝
     - 8192 bytes
   * - 回應終止符
     - ``Return_Data_Over_JE``
   * - 關閉指令
     - ``quit_server``
   * - 執行緒模型
     - 多執行緒（``socketserver.ThreadingMixIn``）
