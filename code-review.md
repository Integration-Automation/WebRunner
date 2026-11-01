# 程式審核：WebRunner

審核者＝工作區程式審核；日期＝2026-10-22；對象＝`WebRunner`（je_web_runner）；結論＝需修正。

## 審核者

工作區程式審核。審核日 2026-10-22。對象為工作樹 `D:\Codes\WebRunner` 的套件 `je_web_runner`（熱點，非逐行）。未改其他檔、未執行測試、未啟動瀏覽器、未匯入套件。

## 審核規範

共通規範在工作區 repo [JE-Chen/Codes](https://github.com/JE-Chen/Codes) 的 `docs/code-review-standard.md`。下面留下 2026-10-22 這次審核所用的條款，讓審核紀錄的依據對得上那一次。之後的審核以工作區那份為準。本專案更嚴的條款仍以本節與本專案的 `CLAUDE.md` 為準。

本專案書面限制更嚴者從嚴（見「本專案加嚴」）。

1. 設計：分層、命令表、閘門與擴充點是否與 `architecture.md` 一致；已有測試的閘門不當缺陷。
2. 可讀性：認知複雜度 ≤ 15、函式 ≤ 75 行（本次委託上限 80，從嚴取 75）、巢狀 ≤ 4、參數 ≤ 7、行 ≤ 120；循環複雜度 ≤ 10、檔案 ≤ 750。
3. 錯誤處理：無裸 `except`；不吞例外；資源要關閉。
4. 死碼：熱點路徑上不留已失效的分支。
5. 型別與 docstring：公開函式要有型別與說明。
6. 安全：套件閘門預設拒絕；`eval`／`exec` 不得對不可信輸入，內建函式只走 `SAFE_BUILTINS`；無 `shell=True`；WebDriver 對不可信 URL 的接收方式；日誌路徑；另禁止 `pickle`、`yaml.load`、`verify=False`、把憑證寫進日誌。
7. 測試：閘門應有測試才視為設計；本次未跑測試，只核對測試是否存在。
8. 效能：熱點上不做全庫掃描；僅在與安全路徑重疊時註記。
9. §6 隱性契約：不建議改公開模組路徑、命令名、CLI 旗標或日誌模組拼字。
10. 文件同步：`architecture.md`、`CLAUDE.md`、README 與 `docs/updates/` 對同一閘門的預設行為要一致。

嚴重度：缺陷（行為與安全約束不符，且動作檔或 MCP 可走到）、建議（預設路徑無立即損害，或只是文件）、備註（設計如此，不列缺陷）。通過＝無未關閉缺陷；有條件通過＝無立即損害；需修正＝有未關閉缺陷。

## 審核紀錄

#### CR-01

- 嚴重度：缺陷
- 位置：`je_web_runner/utils/lighthouse/lighthouse_runner.py` 的 `_build_command`（約第 35–54 行）與 `run_lighthouse`（約第 76–109 行，`subprocess.run` 約第 108 行）；註冊於 `je_web_runner/utils/executor/_event_table.py` 約第 607 行 `WR_lighthouse_run`；MCP 拒絕清單 `je_web_runner/mcp_server/_policy.py` 約第 25–35 行未含此命令。
- 說明：`lighthouse_path` 是 argv 第 0 個元素，`extra_args` 原樣接在命令尾端。`shell` 為假，沒有字串殼層，但動作 JSON 以關鍵字引數呼叫 `WR_lighthouse_run` 時仍可指定可執行檔與附加引數。URL 有 `http`／`https` 檢查，可執行檔沒有。套件閘門擋的是「動作檔匯入 `os` 或 `subprocess`」；這條 `WR_*` 不經過該閘門。`webrunner_run_actions` 使用同一命令表，`UNSAFE_COMMANDS` 只拒絕載入套件、重開腳本閘門與 AutoControl，不拒絕 `WR_lighthouse_run`。預設路徑是名稱 `lighthouse`，一般呼叫不會換成別的程式；不可信動作檔或 MCP 呼叫可以。
- 依據：`CLAUDE.md` 安全要求動作執行器只呼叫已註冊命令，且不得讓不可信輸入經 `subprocess` 取得殼層能力；`architecture.md` §7 與 README 的套件閘門都把「動作檔不得自行取得任意程式」當成威脅模型。`shell=False` 與 `# nosec` 沒有限制 argv 第 0 個元素。
- 狀態：未關閉
- 建議：`WR_lighthouse_run` 不要暴露可替換的可執行檔路徑；若必須保留，只允許檔名為 lighthouse（含平台後綴），並拒絕會改寫程式本體的附加引數。會啟動外部行程的命令應納入 MCP 拒絕清單，或與套件閘門一樣只能由宿主行程開啟。

#### CR-02

- 嚴重度：建議
- 位置：`je_web_runner/utils/api/http_client.py` 約第 54–79 行 `http_request` 的 `**request_kwargs`，以及約第 83–100 行轉發給它的 `http_get` 等；命令表約第 355–360 行 `WR_http_*`。
- 說明：檔頭寫明不關閉憑證驗證，函式本身也沒有傳入關閉驗證的旗標。多出來的關鍵字引數卻整包交給 `requests.request`，動作檔因此可以帶上該函式庫用來關閉驗證的參數。預設仍驗證；這不是預設關閉，而是沒有拒絕。自訂 CA 路徑與此不同，不應一併禁掉。同檔的 OAuth（`utils/auth/oauth.py` 的 `_post_token`）沒有這條通道。
- 依據：`CLAUDE.md` 靜態分析安全項禁止關閉憑證驗證。
- 狀態：未關閉
- 建議：在送出前拒絕代表關閉驗證的值；CA 檔路徑仍可通過。為 `WR_http_*` 補一則拒絕測試。

#### CR-03

- 嚴重度：建議
- 位置：`je_web_runner/utils/executor/action_executor.py` 約第 142–143 行 `_Reporter.on_failure`，約第 395–399 行 `execute_one` 的錯誤日誌。對照 `je_web_runner/utils/auth/oauth.py` 約第 39–42 行（只記 URL）與 `utils/autocontrol_bridge/native.py` 約第 123–141、146–158 行（基本認證拒絕內嵌帳密，且不把值寫進日誌）。
- 說明：`WEBRunner` logger 門檻是 WARNING，所以 `on_start` 的 INFO 整份動作清單不會進檔。失敗時 ERROR 會把整個 action 寫進日誌。`password_grant_token` 等命令的引數若在動作裡，失敗紀錄會帶上憑證欄位。指令自己的 INFO 沒有寫這些欄位，缺口在執行器的失敗日誌，以及結果印到標準輸出時可能含權杖欄位。原生基本認證路徑已避開這個問題。
- 依據：`CLAUDE.md`「憑證不得寫入日誌」；`architecture.md` §6 對基本認證的描述與程式一致，但沒有覆蓋所有 `WR_*`。
- 狀態：未關閉
- 建議：失敗日誌與標準輸出在寫入前遮罩已知憑證欄位名；不要改基本認證那條已設計的路徑。

#### CR-04

- 嚴重度：建議
- 位置：`architecture.md` 約第 3 行（Last verified: 2026-10-11）與 §7 約第 180–183 行。
- 說明：§7 仍寫未設定時任何套件都會載入並發 `DeprecationWarning`，並稱 `progress.md` #22 才會把預設改成拒絕。程式已是預設拒絕：`PackageManager.allow_arbitrary_packages` 初始為 `False`（`utils/package_manager/package_manager_class.py` 約第 25–27、48–57 行），`_check_allowed` 在 `import_module` 之前，開關不是 `WR_*`。`progress.md` 開項只剩 #20。README 套件閘門、`docs/source/Eng/doc/package_manager/package_manager_doc.rst` 約第 49–50 行、`docs/updates/2026-10.md` 的 U-20261001-44 都寫預設拒絕。測試 `test/unit_test/test_package_allowlist.py` 斷言未設定即拒絕且不會匯入。閘門本身不是缺陷；過期的是架構文件。
- 依據：審核規範第 10 條；`architecture.md` §8 要求閘門行為變更時更新該檔。
- 狀態：未關閉
- 建議：刪掉 DeprecationWarning 與「#22 才翻轉」那句，改成與 README 相同的預設拒絕，並更新 Last verified。不要改閘門語意，不要把 `allow_packages` 做成動作命令。

#### CR-05

- 嚴重度：備註
- 位置：`je_web_runner/utils/executor/action_executor.py` 約第 66–75、176–180、357–370 行；`je_web_runner/mcp_server/_policy.py` 約第 10–11、28 行。
- 說明：任意腳本閘門預設開啟（`allow_arbitrary_script = True`），註解寫明為了相容。MCP 拒絕的是 `WR_set_allow_arbitrary_script`，避免呼叫端把宿主關掉的閘門再打開，並不拒絕 `WR_execute_script` 等命令本身。`test/unit_test/test_mcp_security_policy.py` 覆蓋這項。與套件閘門「預設拒絕」不同，但是有測試的設計，不列缺陷。
- 依據：委託說明：設計過且有測試的閘門不當缺陷。
- 狀態：不列缺陷
- 建議：無。若日後要把不可信動作檔的預設改成關閉，須另走棄用政策，並同步 §7 與 MCP 工具說明（該說明目前把 CDP 與 init script 列為可用命令）。

#### CR-06

- 嚴重度：備註
- 位置：`je_web_runner/webdriver/_wrapper_mixins/_navigation_mixin.py` 約第 18–26 行 `to_url`；`je_web_runner/webdriver/_playwright_mixins/_page_mixin.py` 約第 102–107 行；`je_web_runner/utils/async_executor/commands.py` 約第 23–26 行 `goto`；`je_web_runner/utils/multi_tab/choreographer.py` 約第 51–52 行。
- 說明：這些入口把 URL 字串直接交給 `WebDriver.get` 或 Playwright `page.goto`，沒有協定允許清單。有檢查的是別的路徑：HTTP 客戶端、Lighthouse、driver pin、基本認證（僅 `https`，迴路 `http` 例外，且拒絕內嵌帳密）、Playwright context 重建（`_context_mixin.py` 約第 61–63 行只重開 `http`／`https`）、儀表板連結（`live_dashboard/_widgets.py` 的 `safe_link` 拒絕 `javascript:`）。對瀏覽器自動化而言，URL 是動作檔的正常輸入，包含本機測試頁；不把「沒有協定白名單」列成缺陷。不可信動作檔若只關掉腳本閘門，仍可能經導航讀到瀏覽器允許開啟的本機頁，再配合頁面來源命令取回內容。那是產品能力，不是這次要重開的閘門。
- 依據：`architecture.md` §7「驗證外部 URL」與 §6 基本認證那一則；後者已在程式實作，前者沒有落在 `WR_to_url`。
- 狀態：不列缺陷
- 建議：無須改 `WR_to_url` 的簽章（§6 契約：AutoControlGUI 依賴 `WR_to_url`）。若要收緊，應是另加可選政策，而不是改掉現有命令。

### 方法

讀 `architecture.md`（含 §6）、`CLAUDE.md` 安全與長度、`progress.md` 前 80 行（開項只剩 #20）。在 `je_web_runner` 搜尋 `eval(`、`exec(`、`shell=True`、`pickle`、`yaml.load`、`verify=False`、裸 `except`、`subprocess`。每一則發現都先讀過對應程式。排除 `test/`、`build/`、`dist/`、`__pycache__/` 與 `docs/` 產生物；測試只用來確認閘門是否為既有設計。未從工作區外匯入本套件。

### 總評

套件閘門與內建函式允許清單是預設拒絕，而且有測試，維持現狀。沒有 `eval`／`exec`，也沒有 `shell=True`。日誌路徑與 §6 一致。未關閉的缺陷是 CR-01：`WR_lighthouse_run` 讓動作檔與 MCP 指定外部程式，繞過套件閘門想擋住的那類能力。預設參數不會自己換程式，所以不是預設組態下的立即損害，但仍是未關閉缺陷，結論為需修正。CR-02、CR-03、CR-04 不阻擋這次對閘門本身的判斷。

### 已核對

- 套件閘門：`allow_arbitrary_packages` 預設 `False`；`add_package_to_executor` 與 callback 路徑都先 `_check_allowed` 再匯入；`check_package` 本身不查閘門，但套件內只有 `get_member` 呼叫它，而該路徑已先檢查。允許清單用「全名或子模組前綴」，測試拒絕看起來像已允許套件的其他名字。不建議改名或改成動作命令。
- `SAFE_BUILTINS`：`Executor` 只註冊 `je_action_core` 的 `safe_builtin_commands()`。套件內沒有 `eval(` 或 `exec(`。`test/unit_test/test_executor_builtins_allowlist.py` 要求已註冊內建函式等於允許清單，並明確排除 `eval`、`exec`、`compile`、`__import__`、`open` 等。`architecture.md` 的「22 個名字」由 `test/unit_test/test_doc_counts.py` 對允許清單長度把關。這次未匯入套件，沒有重數名單。
- 殼層：套件內沒有 `shell=True`、`os.system`、`os.popen`。`process_supervisor`、`diff_shard`、`test_auto_repair` 的 `subprocess` 都是固定的 argv 清單，且前兩者不在 `WR_*` 表。`--changed-since` 會把 ref 接進 `git diff` 的單一引數（`utils/sharding/diff_shard.py` 約第 45–50 行、`utils/impact_analysis/selection.py`）；操作者已在跑本機 CLI，不另開缺陷。
- 日誌：`utils/logging/loggin_instance.py` 的 `default_log_file` 依序為 `WEBRUNNER_LOG_PATH`、`WEBRUNNER_LOG_DIR/WEBRunner.log`、`~/.je_web_runner/logs/WEBRunner.log`。handler `delay=True`，第一筆紀錄才建目錄。編碼 UTF-8。模組路徑維持 `loggin_instance` 拼字。與 §6 一致，不建議改路徑或改名。import 時把 root logger 設為 DEBUG 已在 §6 標成既有副作用。
- 其他搜尋：無裸 `except`、無 `pickle`、無 `yaml.load`（OpenAPI 用 `yaml.safe_load`）、無字面 `verify=False`（見 CR-02 的轉發）。XML 解析走 `defusedxml`；報告組字用 `html.escape`。driver pin 解壓前檢查成員是否落在目標目錄內（`utils/driver_pin/pinner.py` 約第 164–206 行）；舊解釋器沒有 `filter` 時會退回一般解壓，符號連結目標的註解已寫明，且 pin 檔是宿主設定，不列缺陷。Socket 預設 `localhost`，token 用 `compare_digest`。即時儀表板預設綁 `127.0.0.1`。
- §6：未建議重新命名 `execute_one`、`executor`、`webdriver_wrapper`、`loggin_instance`，或既有 `WR_*`、CLI 旗標。

### 未涵蓋

未逐函式量複雜度、行數與巢狀，因此沒有可讀性缺陷；命令表檔很長，但是登錄表，這次不把它當熱點缺陷。未跑 pytest、pylint、bandit、mypy。未審 `build/`、`docs/` 產生的 HTML、測試本體。未連上 Selenium 或 Playwright 確認各瀏覽器對 `javascript:` 與 `file:` 的實際行為（CR-06 只描述程式把字串交給驅動程式）。`je_action_core` 的允許清單內容以本套件的註冊與測試契約為準，未打開該依賴的原始碼。

### 本專案加嚴

`CLAUDE.md` 函式 ≤ 75 行、循環複雜度 ≤ 10、檔案 ≤ 750，嚴於本次委託的函式 80 行。認知複雜度 ≤ 15、巢狀 ≤ 4、參數 ≤ 7、行 ≤ 120 與委託相同。安全項另加：套件閘門預設拒絕、內建函式允許清單、禁止 `shell=True` 與關閉憑證驗證、憑證不入日誌。公開模組路徑以 `architecture.md` §6 為契約，不建議改名。

### 結論

需修正。未關閉缺陷 1 則（CR-01）。另有建議 3 則（CR-02、CR-03、CR-04）與備註 2 則（CR-05、CR-06）。套件閘門預設拒絕、`SAFE_BUILTINS` 未收錄 `eval`／`exec`、沒有 `shell=True`、日誌路徑與 §6 一致，這些不列缺陷。
