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

隔離本機程式修正
----------------

``CodeProcessor`` 共用本機限定的 Ollama 通訊，提供有大小限制的檔案讀取、
字面文字搜尋、經檢查的 unified patch，以及主機設定的具名檢查。
模型不能執行主機 shell 或發布修改。每個執行使用獨立 clone 與 detached worktree，
不修改正式工作樹。

另行安裝 Podman 與開源本機模型，先建立一次映像：

.. code-block:: bash

    podman build -f docker/IssueWorker.Containerfile -t localhost/webrunner-issue-worker:local .

建置內容排除原始碼工作樹的密鑰與 git 資料。執行時不拉取映像、沒有外網，
採非 root 使用者並移除 capabilities；只掛載不含 .git／憑證檔的唯讀程式快照。
命令 argv 由主機設定，並限制時間及輸出大小。

文字 patch 限於程式、測試、文件與範例；工作流程、相依鎖檔、版本、密鑰、發版及
儲存庫權限規範均受保護。保留既有測試斷言與函式，並攔截新增 skip／xfail。
二進位修改及 rename 語法須人工處理，可用文字刪除／新增搬移檔案。
預設最多 20 個檔案、1000 行變更、100 次工具操作、兩輪驗證與 60 分鐘。
修改前與最後驗證結果均綁定明確 git tree ID，模型宣告完成不能跳過檢查。
