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

執行與審查
----------

支援 bug、新功能、重構、測試與文件。設定本機模型、``OLLAMA_NO_CLOUD=1``，
再重新啟動 Ollama；執行器會確認雲端已關閉且本機權重已安裝。
GitHub token 須有程式庫 Contents／Issues／Pull requests 寫入權限，
且 ``github_bot`` 必須符合登入身分。Jira 須有瀏覽、指派、編輯及留言權限，
並符合設定的 accountId，不需工作流程狀態轉換權限。

.. code-block:: bash

    python -m je_web_runner.issue_worker run --config issue-worker.json --dry-run
    python -m je_web_runner.issue_worker run --config issue-worker.json
    python -m je_web_runner.issue_worker watch --config issue-worker.json
    python -m je_web_runner.issue_worker status --config issue-worker.json
    python -m je_web_runner.issue_worker retry --config issue-worker.json --issue jira:WR-123

``run`` 最多處理一單，``watch`` 預設每 60 秒輪詢。閒置、預演與待審 PR 交付
結束碼為 0；失敗、未完成或平台回報尚未送達為 1，Ctrl-C 為 130。
重試前須恢復 ``automation-ready``，不會搶走其他人的指派。
GitHub 與 Jira 來源都會將 PR 交付到 GitHub 的 WebRunner 程式庫。

Python ``IssueWorker(config)`` 提供 ``run_once``、``watch``、``status``、
``retry``，須於 ``finally`` 呼叫 ``close``。``IssueInbox`` 可只預演或排單。
MCP ``webrunner_issue_enqueue``／``webrunner_issue_status`` 只使用主機設定的
``WEBRUNNER_ISSUE_CONFIG``，不接受呼叫者提供設定路徑、命令或權限變更。

流程狀態為 queued／claimed／analyzing／fixing／validating／publishing／
awaiting_review，另有 needs_info／failed／cancelled 停止狀態。
報告位於狀態目錄下的 ``reports``；SQLite 為權威狀態。檢查點可恢復中斷的
程式修正、綁定 git tree 的驗證與尚未送達的進度回報。
同一狀態目錄不能靜默切換平台網址或程式庫。

修改檢查點與發布前會重新讀取 ready 標籤、指派及人工需求；變更時取消執行。
發布也會拒絕已前進的 dev 基準、未驗證的內容、外部改動的分支或 PR head。
PR 建立成功但回應遺失時，先依分支與執行標記查詢，不會再建立第二個 PR。
進度只更新一則 bot 留言；結束時移除 ready 標籤並標示待審、待補資訊、失敗或取消。
只變更仍指派給預期 bot 的 issue 標籤，不覆寫人工指派。

主機發布器透過 GitHub Git Database API 建立與驗證結果一致的 tree、
可重現的 commit 與專用 automation 分支，再提出送往 dev 的 PR。
Token 不寫入 git 設定、模型提示、容器或報告；系統不合併 PR，也不關閉來源 issue。
人工審查仍須確認行為是否符合需求，測試通過不等於業務需求已被完整證明。
準備映像時可能需要下載相依套件；執行時沒有付費服務備援。

驗證
----

本機整合測試提供 GitHub、Jira 與 Ollama HTTP 模擬端點，並使用真實暫存 git
程式庫重現失敗測試、套用 patch、執行 pytest、建立單一模擬 PR，及恢復遺失的
建立回應。測試不修改真實 issue／PR／Jira 網站。
真實 Podman 檢查為選用：安裝引擎與映像並設定 ``WEBRUNNER_ISSUE_IMAGE``，
再執行 ``test/unit_test/test_issue_coding.py``。此選項才會啟動真實離線容器，
一般 HTTP 模擬測試不宣稱已驗證容器隔離。

MCP 伺服器建立工具時會解析並固定 issue 設定；修改主機設定後須重新啟動。
其他工具載入環境變數時，不能改變這些 issue 工具的設定。分頁防護會拒絕重複
結果頁與跨頁 token 循環，避免無限輪詢。

啟用前請備妥 GitHub 程式庫標籤：``automation-ready``、``automation-running``、
``automation-review``、``automation-needs-info``、``automation-failed``、
``automation-cancelled``。Jira 使用相同標籤名稱。
