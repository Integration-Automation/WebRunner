本機 Issue Worker
=================

接單條件為 GitHub／Jira Cloud 中帶有 ``automation-ready``、尚未指派且未結案的
issue，並排除 GitHub PR。程式庫固定為 ``Integration-Automation/WebRunner``，
審查目標為 ``dev``。Jira 須明確設定專案白名單與帳號 ID，不假設工作流程狀態名稱。

複製 ``examples/issue-worker.example.json``，設定已安裝的本機模型、bot 身分與
Jira 網站。只使用 GitHub 時，移除 Jira 網址、專案與 bot 欄位。
憑證設定只填環境變數名稱，不在 JSON 放入金鑰值。相對狀態路徑以設定檔位置解析。
SQLite WAL 保存佇列與檢查點，透過可續租的單一 worker 租約協調同一主機上的處理。

.. code-block:: python

    from je_web_runner.api.orchestration import IssueInbox, IssueWorkerConfig

    inbox = IssueInbox(IssueWorkerConfig.load("issue-worker.json"))
    try:
        print(inbox.discover(dry_run=True))  # 只讀平台，不建立佇列工作
        inbox.discover()  # 排入合格 issue，不在平台認領
    finally:
        inbox.close()

輪詢不會覆寫處理中的需求快照。需求版本取決於人工描述與留言，不含 bot 進度。
失敗、取消或待補資訊的工作，須恢復 ready 標籤並明確重試。
平台 HTTP 拒絕重新導向，不盲目重試寫入，並以不含回應本文或憑證的錯誤回報限流。
既有 Jira 建立 issue API 維持相容。
