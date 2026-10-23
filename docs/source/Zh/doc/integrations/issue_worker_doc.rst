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
結束碼為 0；失敗、環境暫停或平台回報尚未送達為 1。watch 第一次 Ctrl-C
停止接單並完成當前工作，第二次強制中斷，結束碼為 130。
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

啟用診斷與健康狀態
------------------

先診斷，再預演、手動一單，最後才啟用常駐：

.. code-block:: bash

    python -m je_web_runner.issue_worker doctor --config issue-worker.json
    python -m je_web_runner.issue_worker doctor --config issue-worker.json --platform --json
    python -m je_web_runner.issue_worker health --config issue-worker.json --json
    python -m je_web_runner.issue_worker stop --config issue-worker.json

``doctor`` 檢查 Git、可寫狀態目錄／SQLite、Podman 引擎與既有映像，以及本機
Ollama 的雲端停用狀態及已安裝模型。不執行模型生成，不下載、不安裝、不啟動服務。
會建立並清除暫存的本機 SQLite 探針，但不建立工作佇列。
``--platform`` 才讀取真平台，確認 GitHub 身分、儲存庫、dev 與六個標籤，以及
Jira 身分與所有白名單專案；Jira 標籤可自由使用，沒有預先建立的標籤目錄。
所有平台請求皆為 GET，不認領、不留言；完整寫入權限明列為未驗證。
必要檢查皆通過時結束碼為 0，否則為 1。JSON 包含 ready、checks，以及各項
name／status／required／code／hint，不含原始 HTTP 本文或子程序錯誤輸出。

``health`` 只讀本機營運狀態；首次使用可能初始化本機資料表，不連接平台或模型。
healthy 回傳 0，degraded 回傳 1，stopped／stale 回傳 2。JSON 顯示執行個體、
PID、啟動時間、心跳、當前階段／issue、最近完成輪詢、錯誤及停止請求。
心跳獨立於模型及容器，每 10 秒更新，超過 45 秒視為過期。
``stop`` 完成請求時回傳 0；沒有活躍程序時輸出 stop_requested=false，不留下
未來的停止標記。當前單依原有期限完成，正常排空後退出；閒置輪詢等待每 250 ms
檢查停止請求，正在進行的診斷或 HTTP 請求仍受各自逾時約束。

watch 在每次接單前檢查本機必要條件，依賴故障時暫停接單、每個輪詢週期重查。
修正期間發生模型／容器基礎服務故障時，工作保留可恢復狀態；既有每單總期限
不因停機延長。常駐租約與工作租約分開，同一目錄只允許一個 watch，並拒絕另一個
手動 run。新的 worker_runtime 資料表不修改既有工作狀態。
容器加上狀態目錄摘要標籤；取得工作租約後，只清除相同標籤及專用名稱的中斷容器，
不清除其他工作或人工容器。doctor 不執行此清理。
日誌位於狀態目錄 logs/worker.log，每檔 5 MB、保留五份備份，不寫入需求或模型
對話，也不自動清除工作目錄及歷史報告。

Python ``IssueDoctor(config).check(include_platform=False)`` 提供相同診斷；
``IssueWorker.health()``／``request_stop()`` 提供本機健康及排空控制。
MCP 仍只提供排單及查詢，不增加執行或停止工具。

Windows 登入常駐
----------------

使用與手動執行相同的使用者環境提供憑證，並先準備好模型、Podman 及映像。
排程不保存金鑰，只保存 Python／腳本／設定檔的絕對路徑。

.. code-block:: powershell

    .\scripts\issue_worker_task.ps1 -Action Install -Config .\issue-worker.json
    .\scripts\issue_worker_task.ps1 -Action Start -Config .\issue-worker.json
    .\scripts\issue_worker_task.ps1 -Action Status -Config .\issue-worker.json
    python -m je_web_runner.issue_worker stop --config issue-worker.json
    # 等待排程停止後移除；不強制終止工作。
    .\scripts\issue_worker_task.ps1 -Action Remove -Config .\issue-worker.json

預設 Python 為此 checkout 的 .venv\Scripts\python.exe，可用 ``-Python`` 指定。
腳本位置及 checkout 必須持續存在。任務名稱由設定路徑摘要產生，只操作自己建立的
任務；目前使用者登入時觸發、一般權限、隱藏視窗、忽略重複啟動，異常退出每分鐘
重試、最多三次，不設執行時間上限。Install 不會立即啟動，使用者須保持登入；
不提供登出後仍運作的系統服務，也不自動啟動 Ollama 或 Podman。
正在執行的任務須先排空，才能更新或移除。

必要的真實本機驗收
------------------

一般測試可略過真實環境；專用入口在缺少環境時失敗，不將略過算成驗收成功：

.. code-block:: powershell

    $env:WEBRUNNER_ISSUE_MODEL = 'YOUR_INSTALLED_LOCAL_MODEL'
    $env:WEBRUNNER_ISSUE_IMAGE = 'localhost/webrunner-issue-worker:local'
    python scripts/verify_issue_worker.py --soak-hours 0
    python scripts/verify_issue_worker.py  # 真實端到端＋預設 24 小時常駐驗收

僅模型和容器使用真實服務；GitHub／Jira 全部使用本地測試 HTTP 端點。
驗收覆蓋兩種來源、失敗基準與修正後通過、PR 回應遺失後恢復，並驗證容器非 root、
來源與根目錄唯讀、無平台憑證及無外網。常駐驗收加入 429／503、閒置與反覆停止／
重啟；另有獨立程序測試驗證崩潰、租約接手及 CLI 停止。
Windows 排程的真實臨時註冊／移除測試以 ``WEBRUNNER_TEST_SCHEDULER=1`` 啟用，
不啟動該任務，不修改正式排程。
未安裝 Podman／模型或未完成 24 小時測試時，必須分別標示為尚未驗收。

PR 審查修正循環
---------------

設定 ``review_enabled=true`` 後，run／watch 在沒有進行中工作時，輪詢已交付的
待審 PR，再繼續接新單。舊設定預設不啟用；範例設定明確開啟。
``review_poll_seconds`` 預設 60 秒，``max_review_rounds`` 預設三輪。
只有同一個 bot、同一個執行標記、儲存庫與 automation 分支的 PR 才能續修。

可處理目前 head 上的 CHANGES_REQUESTED／COMMENTED 審查與其行內留言，
以及以 ``/webrunner fix`` 開頭的 PR 一般留言。人員須為 User 類型，且 API 確認
具有 write／maintain／admin 權限；機器人及讀取權限的留言不觸發修正。
同一人的後續核准／撤回會取代舊審查。也接收目前 head 的失敗 check runs 與
最新 commit statuses；不下載外部日誌、不重新執行遠端 CI、不新增付費服務。
Token 除原有寫入權限外，須能讀取 PR 審查、檢查、commit statuses 及人員權限。

每筆最多 4,000 字、每批最多 50 件及 20,000 字回饋；超限時停止並要求整理，
不會截斷要求後宣告完成。先遮蔽憑證並以 SQLite 原子保存、去重，再交給
本機模型作為需求資料，不能改寫主機命令或權限。每輪使用獨立 worktree，以既有
PR head 為 parent，重新取得整套驗證；檔案／行數上限仍以最初 dev 為累計基準。
修正以非 force fast-forward 更新原分支，不另開 PR、不合併、不關閉來源 issue，
並在原 PR 附上一則該輪的驗證留言，不覆寫人工編輯的 PR 本文。
分支更新或留言成功但回應遺失時，先對帳，不重跑模型或重複發布。

修正期間會重查來源需求、指派、PR head 及開啟狀態。來源須仍指派給 bot 並帶有
automation-review／automation-running；移除這些標籤可取消。人工改動 PR head、
dev 前進、PR 關閉或達到輪數上限時停止自動續修，狀態的 review_blocked／
review_closed 說明原因。修正本身失敗或需補資訊時，保留 PR 供人工接手；
不會利用既有 retry 另開重複 PR。

人工補充或修復環境後，可恢復來源的 automation-review 標籤，再執行
``retry-review --config issue-worker.json --issue github:123``（Jira key 亦可）。
此明確操作接受新的來源需求快照、保留同一 run／PR，重新接收未完成回饋，
但仍拒絕外部 head、已關閉 PR、未送達進度及超過主機輪數上限；不寫入平台。
Python 對應為 ``IssueWorker.retry_review(key)``。輪數用盡須先由操作者明確調高
主機設定，不可由模型解除。
