==================================
進階模組
==================================

WebRunner 在 ``je_web_runner/utils/`` 下提供大量專用模組,每一個都是
獨立的 subpackage 並附有完整單元測試。這些模組不在 executor 的核心
路徑上 —— 依需要 import 即可,不會造成額外負擔。

每個模組同時也可透過 ``WR_*`` action JSON 指令呼叫(只要對應的進入
點有註冊)。指令註冊機制請參考
:doc:`../action_executor/action_executor_doc`。

.. contents:: 本頁目錄
   :local:
   :depth: 2

----

Web 平台 API
============

針對現代瀏覽器 API(串流、儲存、檔案選擇器、通知),這些 API 不易透
過原生 WebDriver 操作。

``webtransport_assert``
-----------------------

HTTP/3 WebTransport datagram + stream frame 錄製器。與
``websocket_assert`` 和 ``sse_assert`` 採用對稱 API,無論底層協定如
何,斷言寫法都一致。

主要進入點:

* ``WtFrameRecorder.record_sent_datagram(payload)``,
  ``.record_stream_chunk(direction, stream_id, payload, fin=…)``
* ``assert_datagram_count``、``assert_stream_complete``、
  ``assert_payload_contains``、``assert_json_shape``

``indexed_db_explorer``
-----------------------

產生瀏覽器端 JS,把指定 IndexedDB 序列化成 JSON 回傳;搭配
:class:`IdbSnapshot` 解析器與 ``assert_store_present`` /
``assert_record_count`` / ``assert_key_present`` /
``assert_index_present`` / ``diff_snapshots`` 斷言。

``file_system_access``
----------------------

JS shim 模擬 ``showOpenFilePicker`` / ``showSaveFilePicker`` /
``showDirectoryPicker``。每次對 fake save handle 的 ``write()`` 呼叫
都會記錄到 ``window.__wr_fsa_writes__``;以 ``parse_writes`` +
``assert_wrote`` + ``combined_payload`` 取回斷言。

``notifications_audit``
-----------------------

安裝 JS shim 追蹤每次 ``Notification.requestPermission`` 與
``new Notification(...)`` 呼叫。斷言:

* ``assert_no_prompt_without_gesture``
* ``assert_no_prompt_before(min_page_age_ms=…)``
* ``assert_no_spam_after_deny``
* ``assert_notification_shown(title_contains=…, body_contains=…, tag=…)``
* ``assert_unique_tags``

``sse_assert``
--------------

Server-Sent Events wire-format 解析器 + 緩衝串流的
:class:`SseRecorder`。斷言:數量、data 包含、JSON shape、id 嚴格遞增。

``websocket_assert``
--------------------

WebSocket frame 錄製器 + count / payload / pubsub-pattern /
JSON-shape 斷言。

``webrtc_assert``
-----------------

接受 ``RTCPeerConnection`` 狀態與 ``getStats()`` JSON snapshot。
斷言:連線狀態、track 存在、SDP codec、packet-loss 比例、
最少 byte 流量。

``view_transitions``
--------------------

JS 注入腳本錄製每次 ``document.startViewTransition`` 生命週期與該
window 內的 ``LayoutShift``。斷言:``assert_all_finished``、
``assert_under_duration``、``assert_cls_under``、
``assert_group_present``。

安全與 Headers
==============

``mixed_content_audit``
-----------------------

HAR 解析器 + console 訊息掃描,找出 HTTPS 頁面內載入的 HTTP 資源。
嚴重度分級:``ACTIVE``\ (直接被擋)/ ``PASSIVE``\ (載入但不安全)/
``UPGRADE``\ (HSTS 自動升級)。

``clickjacking_audit``
----------------------

結合 header 政策判定(``X-Frame-Options`` + ``frame-ancestors``)與
HTML probe 頁面產生器 —— 即使 header 看起來正確,仍能實測瀏覽器行為。

``open_redirect_detector``
--------------------------

八種 payload 探測:``//evil``、``@userinfo``、``javascript:``、
``data:``、大小寫繞過、反斜線繞過等。依使用者提供的 probe callable
回傳結果分類為 ``BLOCKED`` / ``ALLOWED`` / ``AMBIGUOUS``。

``sri_verify``
--------------

解析 ``<script>`` / ``<link rel=stylesheet>`` 標籤並驗證
``integrity=``:有沒有設、演算法強度(拒絕 sha1 / md5)、cross-origin
要求,以及(可選)重新計算 hash 驗證。

``coop_coep_audit``
-------------------

審核讓 ``crossOriginIsolated`` 為 true 所需的四個 header
(COOP / COEP),以及每個子資源是否有 ``Cross-Origin-Resource-Policy``
或符合 COEP 的 CORS。

``token_leak_detector``
-----------------------

掃描 HAR body、log lines、任意文字內洩漏的憑證:

* JWT(含 Base64 header 有效性檢查)
* AWS access key + secret 賦值
* GitHub PAT(``ghp_…`` / ``gho_…``)
* Slack bot token(``xox[abprs]-…``)
* Stripe live secret(``sk_live_…``)
* Google API key(``AIza…``)
* Bearer header、session-token 賦值

``consent_audit``
-----------------

知名 vendor cookie 目錄(Google Analytics、Facebook Pixel、Hotjar、
LinkedIn、Mixpanel、Amplitude、Stripe、Intercom、CSRF、session)。
偵測同意前載入的 non-essential cookie 與拒絕後又重新植入的 cookie。

``pii_in_screenshot``
---------------------

對截圖做 OCR + 個資 regex 掃描:email、Luhn-驗證 信用卡、SSN、
ROC ID、IBAN、IPv4、E.164 phone。適合會上傳到共享 dashboard 的截
圖 bundle 把關。

效能預算
========

``inp_tracker``
---------------

Interaction-to-Next-Paint 量測:``PerformanceObserver`` 訂閱
``event``-timing + ``first-input``,依 Web Vitals 門檻分級
(≤200ms GOOD、≤500ms NEEDS_WORK、其餘 POOR)。

``hydration_check``
-------------------

SSR hydration mismatch 偵測。DOM diff 會去除 React / Vue / Svelte /
Astro / Nuxt 框架的特殊 attribute / comment marker,另外掃描 console
訊息中的常見 marker 字串。

``bundle_budget``
-----------------

每種資源類別的傳輸 byte 預算(script / stylesheet / image / font /
media / xhr)。輸入是 HAR;輸出有每類總量、每筆預算違規詳情、以
及最大資源排名。

``third_party_budget``
----------------------

Vendor 分類 + 每 vendor 的請求數 / byte / blocking-ms 預算,加上
總 vendor 數上限。內建常見 analytics / marketing / CX vendor;以
``extra_vendors`` 擴充。

``long_animation_frame``
------------------------

訂閱 ``long-animation-frame`` PerformanceObserver,擷取每個 script
歸因(forced reflow 時間、pause 時間、source URL)。斷言:單一 frame
最大值 + 總 blocking 時間。

``console_error_budget``
------------------------

JS console error / unhandled-rejection 預算,搭配 regex 忽略
patterns。內附 Selenium 與 CDP 事件 payload 兩種 adapter。

後端整合
========

``grpc_tester``
---------------

gRPC stub method 包裝,每次呼叫都記錄到 :class:`GrpcCallRecorder`,
含 status / duration / error。另提供 length-prefix encode / decode 與
trailer 解析助手供 gRPC-Web 使用。

``webhook_receiver``
--------------------

純 stdlib 的 threaded HTTP server(隨機選 port)用來在測試中接 app
對外送出的 webhook。``wait_for(predicate, timeout)`` 加上
``assert_received_path`` / ``assert_received_with_header`` /
``assert_received_json_matching``。

``idempotency_check``
---------------------

把同一個請求送兩次,比對 status code、body(可用
``ignore_body_keys`` 忽略非決定性欄位)、state(透過 ``state_probe``
callable)、副作用次數。``allow_status_change_to`` 處理合法的第二
次 409。

``pagination_audit``
--------------------

透過使用者提供的 :class:`PageFetcher` 一路翻到結束。回報跨頁重複、
cursor loop、empty page index、命中 max_pages,以及跨頁邊界的
``assert_sorted_by`` 排序檢查。

``backend_log_correlator``
--------------------------

UI 跑時擷取 W3C ``traceparent``,從 Grafana Loki / Elasticsearch /
JSON-lines 檔案抓取符合的 log line,並 ``attach_to_failure_bundle``。

``email_render``
----------------

MailHog / Mailpit fetch(或本機 ``.eml`` 目錄)→ 型別化
:class:`CapturedEmail` → 透過可插拔的 render driver 取多 viewport
截圖。

AI / 工作流
===========

``failure_narrator``
--------------------

讀取 failure bundle 資料夾(meta.json + console.log + dom.html +
network_errors.log),交給 LLM 產生自然語言的「為什麼失敗」報告。
回傳必須符合嚴格 JSON envelope;``markdown()`` 產生 PR comment 可用
的字串。

``repro_minimizer``
-------------------

Classic delta-debugging (ddmin):給定失敗 action list 與「會不會還
是失敗」callable,回傳最小的仍會失敗子序列。

``locator_hardener``
--------------------

啟發式 fragility 評分(nth-of-type / text-xpath / hashed-class /
deep-descendant / multi-class CLASS_NAME),再向 LLM 索取更穩的替代
selector。回應有 safety filter 把不安全的 selector 過濾掉。

``test_categorizer``
--------------------

依 action name pattern 的 regex 規則,自動把每個 test 標記為
``smoke`` / ``regression`` / ``perf`` / ``a11y`` / ``security`` /
``payment`` / ``data_driven`` / ``visual`` / ``api`` 中的若干。可
新增自訂 :class:`Rule` 擴充。

``exploratory_ai``
------------------

代理式探索測試員:``Explorer.run()`` loop 驅動 ``PageObserver`` +
``ActionPlanner`` protocol pair,蒐集 console / network error 為
:class:`BugSignal`。內附 ``RandomPlanner`` 作為確定性 fuzz fallback。

``story_to_actions``
--------------------

LLM 把使用者故事(加上選填的 Figma frame metadata)轉成已驗證的
WR action JSON。驗證器會拒絕不認得的 action name 與不合法的 locator
strategy。

``session_to_test``
-------------------

rrweb / 通用 event stream → WR action JSON;自動偵測輸入格式。
無法對映到已知 action 的事件會 fallback 成 ``WR_comment``。

``test_auto_repair``
--------------------

LLM 依 failure bundle + git diff 重寫測試。

``edge_case_generator``
-----------------------

LLM 邊界案例變體產生器(與 ``mutation_testing`` 互補)。

``multimodal_qa``
-----------------

把截圖 + 問題送給 vision LLM(Claude Vision / GPT-4o / 本機 VLM);
嚴格 JSON envelope;``assert_passes(min_confidence=0.6)`` 作為 gate。

``prompt_drift_monitor``
------------------------

針對 app 內建的 LLM 功能:擷取一份 prompt → answer 的 baseline
(含 embedding 與 must_include / must_exclude 詞錨),日後定期
``check_drift(...)``。

``test_dedup_ai``
-----------------

結構性指紋(canonical action signature + 穩定 hash)加上語意去重
(cosine clustering 搭配可插拔 embedder)。

``walkthrough_docs``
--------------------

從錄製到的 run 產生 step-by-step SOP / Confluence 風格的 markdown。

無障礙 / 國際化 / 視覺
======================

``ocr_assert``
--------------

以 Tesseract 為底的文字斷言(``contains`` / ``fuzzy`` / ``any``),
適合 canvas / WebGL / 圖片內文字。內建空白與重音字元正規化;雲端
OCR 也可透過 :class:`OcrBackend` protocol 接上。

``screen_reader_runner``
------------------------

走訪 accessibility tree(CDP ``Accessibility.getFullAXTree`` 或
Playwright snapshot),模擬 NVDA / VoiceOver 朗讀順序。標出沒有
accessible name 的 interactive、heading 層級跳躍、缺 ``alt``、
通用 link text(「click here」、「more」)。

``pseudo_localization``
-----------------------

把字串偽本地化(``__éxámplé strîng__``),同時保留 ``{name}`` /
``%d`` / ``<tag>`` placeholder。``scan_for_hardcoded`` 找出儘管已
偽本地化、仍以原文出現在頁面上的字串(代表很可能是 hard-coded)。

``forced_colors_mode``
----------------------

四個 CSS media query(``color-scheme``、``reduced-motion``、
``forced-colors``、``prefers-contrast``)的 CDP features 產生器。
搭配 computed-style diff 加上「變成隱形」的啟發式偵測。

``visual_ai``
-------------

aHash / dHash / pHash + SSIM-proxy,適合 canvas / chart 的視覺差異。

治理與報告
==========

``pr_risk_score``
-----------------

融合 flake / impact-analysis / locator-health / coverage 訊號,計算
0-100 的 PR risk score。``is_blocking(block_at=75)`` gate 加 markdown
報告。

``flag_matrix``
---------------

Feature flag 組合矩陣,支援 ``forbid`` / ``require`` constraint、
pinned baseline、確定性 seeded 取樣,以及最小失敗子集的 greedy 覆
蓋算法(常見用途:「所有失敗都涉及 checkout=v2」)。

``chaos_hooks``
---------------

種子化的混沌注入:network offline / network slow / CPU throttle /
中途 reload / tab background。同一 seed 對同一 action list 永遠產
生同樣的排程。

``db_snapshot``
---------------

每個 test 的 DB savepoint / rollback 隔離。可插拔的
:class:`SnapshotBackend` protocol;內附 :class:`InMemoryBackend`
方便先測 workflow 本身,context manager 與 pytest fixture factory
皆已提供。

``time_freezer``
----------------

CDP 注入腳本,把 ``Date``、``Date.now``、``performance.now`` 換成
凍結或慢動作的時鐘 —— 對「橫跨午夜過期」、「session timeout」、
「week-of-year 計算」等 bug 特別有用。

``persona_runner``
------------------

驅動「test_case × 角色」矩陣。``summary`` 標出角色專屬的退化(只
有某角色失敗)與檔案專屬的退化(每個角色都在同一個 test 失敗)。

``git_bisect_flake``
--------------------

兩種模式:

* **Ledger-only** —— 直接在標準 run ledger 上計算,不需 git 存取
* **Probe-driven** —— 經典 bisect,接受 ``known_good`` /
  ``known_bad`` 把搜尋區間先夾起來

``test_cost_estimator``
-----------------------

每個 runner 的費率(內建 Sauce / BrowserStack / LambdaTest /
GitHub Actions Linux + macOS 預設值)× ledger 分鐘數 → USD + CO₂
估算,並提供每 test 細目與最貴 N 個 test 的 markdown 報告。

``slack_digest``
----------------

產生 Slack Block-Kit payload(同時也有 Teams Adaptive Card 與純文
字 fallback),整理 quarantine 變動、top-risk PR、cost 趨勢、
pass-rate 差距等資訊。

``quarantine_age_report``
-------------------------

讀 quarantine registry;為每筆條目加上 age 與 tier
(``fresh`` / ``lingering`` / ``stale`` / ``abandoned``)。
``assert_no_abandoned`` 對超過 90 天的條目 raise。

``test_debt_dashboard``
-----------------------

掃描測試樹找 ``@pytest.mark.skip`` / ``skipif`` / ``xfail`` 標記、
測試 body 內的 ``# TODO`` / ``# FIXME``、以及 JSON 內
``"_skip": true`` 標記。同時帶入 age(mtime)與 owner(CODEOWNERS)。

``sla_tracker``
---------------

「Y% 的 suite 在 X 秒內跑完」依 ISO 週或日做 bucket。比對目標
pass 百分比;``assert_meets_sla`` 是 CI gate。

``bug_repro_stability``
-----------------------

把失敗的 probe 重複 N 次 → 分類成 ``deterministic`` / ``flaky`` /
``non_reproducible``。會把 error signature 分組,追蹤最長的 pass /
fail streak。

``test_owners_map``
-------------------

CODEOWNERS 解析器(GitHub 語意:最後一條 match 的規則勝出)+ 每
個 test 的覆寫層(JSON)。``audit_unowned(test_ids, map)`` 列出沒
有對應 owner 的 test。

早期治理 / 品質模組(交叉索引)
------------------------------

``failure_triage``、``flake_detector``、``locator_health``、
``mutation_testing``、``live_dashboard``、``test_scheduler``
已在 :doc:`../quality_security/quality_security_doc` 與
:doc:`../observability/observability_doc` 介紹過;此處再次列出
方便檢索。

其他專用模組
============

* ``chrome_profile`` —— 持久化 Chrome profile + stealth + snapshot
  / sync-back。
* ``device_cloud`` —— 真實裝置雲端連接器(BrowserStack / Sauce /
  LambdaTest)。
* ``otel_bridge`` —— W3C traceparent 注入,串接分散式追蹤。
* ``otp_interceptor`` —— MailHog / Mailpit / IMAP / SMS OTP polling,
  用於 2FA 流程。
* ``download_verify`` —— PDF / CSV / Excel / JSON / SHA256 下載斷言。
* ``openapi_to_e2e`` —— OpenAPI / Swagger 規格 → ``WR_http_*`` action
  JSON 產生器。
* ``cross_tab_sync`` —— 多分頁 BroadcastChannel / storage 傳遞斷言。

現代瀏覽器 API
==============

涵蓋難以用純 WebDriver 驅動的新瀏覽器表面:

* ``popover_assert`` —— ``<dialog>`` / popover 開合 / invoker /
  「同時只有一個 modal」斷言。
* ``cookie_store_api`` —— 非同步 ``cookieStore`` API 擷取 + change
  事件斷言 + secure-only 強制。
* ``speculation_rules`` —— Speculation Rules(``prerender`` /
  ``prefetch``)驗證,prerender 啟動偵測、no-double-fire。
* ``web_locks`` —— 多分頁 Web Locks 競爭測試,含 deadlock /
  serialise / acquired-count 斷言。
* ``storage_buckets`` —— Storage Buckets API 隔離、durability 提示、
  IDB-per-bucket 隔離檢查。
* ``hydration_streaming`` —— 串流 SSR 每個 boundary 的 timing
  (arrival、interactive)+ 順序斷言。
* ``web_push_assert`` —— Push subscription VAPID key 匹配、endpoint
  白名單、``userVisibleOnly``、``showNotification`` payload。
* ``background_sync_assert`` —— Background Sync register / fire /
  retry / ``lastChance``(quota 耗盡)斷言。
* ``wake_lock_assert`` —— Screen wake lock acquire / release /
  漏掉 / 切回前景時 re-acquire 偵測。
* ``pip_assert`` —— Picture-in-Picture(影片 + Document PiP)
  進入 / 離開 / 視窗尺寸斷言。
* ``web_share_assert`` —— ``navigator.share`` payload 紀錄 +
  fallback UI 斷言。
* ``compression_streams`` —— ``CompressionStream`` gzip / deflate /
  brotli 來回 + 壓縮率預算。
* ``compute_pressure`` —— Compute Pressure API 假 observer + App
  throttle 反應斷言。

現代認證 / 支付 / 身分
======================

* ``webauthn_mock`` —— 用於 Passkey / FIDO2 / WebAuthn 流程的
  ``navigator.credentials`` 確定性 shim;依使用者構建固定 credential。
* ``credential_management`` —— Password / Federated Credential
  Management API mock + autofill / ``preventSilentAccess`` 斷言。
* ``payment_request_assert`` —— Payment Request API shim + Apple
  Pay / Google Pay 結帳片驗證(幣別、運送、``complete()``)。
* ``three_d_secure_flow`` —— 3-D Secure 2.x 分支模型
  (frictionless / challenge / fallback / reject)+ 「靜默完成」
  偵測。

行動瀏覽器專屬
==============

* ``touch_gesture`` —— ``tap`` / ``swipe`` / ``pinch`` /
  ``long_press`` CDP frame builder + event 斷言。
* ``viewport_audit`` —— viewport meta + safe-area-inset 稽核 +
  WCAG 1.4.4 user-scalable 稽核。
* ``virtual_keyboard`` —— ``visualViewport`` before / after +
  keyboard inset CSS 變數 + focused element 可見性。
* ``pull_to_refresh`` —— ``overscroll-behavior`` + 觸發 threshold +
  refresh handler + 網路 refetch 斷言(PWA)。

LLM / AI 功能測試
=================

* ``rag_grounding_assert`` —— RAG 引用是否在 retrieved chunk 中、
  詞彙重疊度、未支撐的 phrase 掃描。
* ``llm_token_cost_tracker`` —— 每個 test 的 token / $ 帳本,
  含 per-model 費率卡 + 預算斷言。
* ``streaming_chat_assert`` —— TTFT / inter-token gap / UTF-8 乾淨度
  / 重複或亂序 chunk 斷言(streaming chat)。
* ``tool_call_assert`` —— LLM tool / function-call 的名稱 + 順序 +
  JSON Schema 引數驗證。
* ``hallucination_probe`` —— Ground-truth probe runner + 拒答偵測
  + 幻覺率預算。

Email 與通知送達
================

* ``email_deliverability`` —— SPF / DKIM / DMARC header +
  ``List-Unsubscribe``(Gmail/Yahoo 大量寄件規則)+ BCC 外洩稽核。
* ``inbox_render_outlook`` —— Outlook(Word 引擎)/ Gmail / Apple
  Mail 渲染相容性 pre-flight 檢查。
* ``push_delivery`` —— FCM / APNs payload 大小 + 必填欄位 + PII
  掃描 + collapse key + TTL 驗證。

效能預算(續)
==============

* ``memory_pressure_emulate`` —— CDP 記憶體 / CPU 壓力模擬 profile
  + run-under-profile 斷言。
* ``third_party_block_test`` —— 逐 vendor 的封鎖韌性矩陣
  (no-vendor / blocked / passed)。
* ``bundle_diff_pr`` —— PR bundle 差異(新增 / 移除 / 長大)+
  成長閘 + markdown 報告。
* ``lcp_image_audit`` —— LCP 圖片有 preload + 無 ``loading="lazy"``
  + ``fetchpriority="high"`` 斷言。
* ``font_loading_strategy`` —— ``@font-face`` ``font-display``
  策略 + ``size-adjust`` fallback 的 FOUT / FOIT / FOFT 驗證。
* ``resource_hints_audit`` —— ``preload`` / ``prefetch`` /
  ``preconnect`` 實際使用 vs 宣告 + ``preload as=`` 驗證。
* ``critical_css_audit`` —— Inline CSS in ``<head>`` 預算 +
  render-blocking 外部樣式 preload 稽核。
* ``lighthouse_regression`` —— Lighthouse 分數對 baseline 的退化 +
  Core Web Vitals metric 預算。

安全與標頭(續)
================

* ``prompt_injection_scanner`` —— LLM jailbreak payload 庫 +
  canary 外洩偵測。
* ``cors_matrix`` —— CORS preflight 矩陣 probe + credentials /
  origin policy 斷言。
* ``oauth_pkce_replay`` —— 確認授權伺服器會拒絕 replay 的 OAuth
  state / PKCE verifier。
* ``cookie_chips_audit`` —— CHIPS Partitioned cookie 合規性
  (第三方需 Partitioned + Secure + SameSite=None)。
* ``sbom_diff`` —— CycloneDX SBOM 差異(新增 / 移除 / 升級 /
  授權 / 漏洞閘)。
* ``webhook_signature_verify`` —— GitHub / Stripe / Slack / 通用
  HMAC webhook 簽章驗證。
* ``dom_xss_taint`` —— 透過 JS instrumentation + canary 的輕量級
  DOM-XSS taint 追蹤。
* ``csp_violation_parser`` —— CSP ``report-uri`` / ``report-to``
  payload 解析 + 偵察行為啟發式。
* ``hsts_preload_audit`` —— HSTS preload-list 合規
  (``max-age`` ≥ 1y + ``includeSubDomains`` + ``preload``)。
* ``tls_cipher_audit`` —— 實際 TLS 握手 + 版本 + cipher 白名單 +
  憑證 subject 檢查。
* ``cookie_scope_abuse`` —— session-like cookie scope(apex domain
  / ``Path=/``)+ ``HttpOnly`` / ``Secure`` / ``SameSite`` 稽核。

後端整合(續)
==============

* ``graphql_n_plus_1`` —— GraphQL 的 N+1 query 偵測 + 笛卡兒 fanout
  啟發式。
* ``mq_assert`` —— Kafka / RabbitMQ / SQS 風格的 message queue
  publish 斷言(drain + matcher + 冪等 + 順序)。
* ``grpc_streaming_assert`` —— gRPC streaming(unary / server /
  client / bidi)frame 數 + 大小 + 順序 + half-close 斷言。
* ``openapi_drift`` —— 線上 API vs OpenAPI spec 漂移
  (未文件化的 endpoint / method / status、zombie endpoint)。
* ``api_version_compat`` —— 舊 client × 新 server 向後相容矩陣
  (response shape 與 required request fields)。
* ``rate_limit_assert`` —— 429 + ``Retry-After`` + ``X-RateLimit-*``
  單調 + 等候後恢復斷言。
* ``har_to_openapi`` —— HAR → OpenAPI 3.1 反向工程
  (path template、query 參數、response schema)。

QA 治理與 DevX(續)
====================

* ``failure_auto_tag`` —— 啟發式 + LLM 的失敗自動標籤
  (``flaky-locator`` / ``timeout`` / ``js-error`` / ``network-5xx``)。
* ``test_self_describe`` —— 從 action JSON 反推 Gherkin
  ``Given / When / Then`` 段落。
* ``pr_title_generator`` —— 從 diff + commit history 產生
  Conventional Commits 風格的 PR 標題。
* ``action_refactor_suggester`` —— Action JSON 重構壞味
  (hard sleep、positional XPath、重複的 locator、click-wait-click)。
* ``test_roi_scorer`` —— 「找出 bug 機率 × 成本 × 涵蓋 × 新鮮度」
  加權的每個 test ROI 分數。
* ``pre_merge_gate_dsl`` —— 對 ``PrFacts`` 快照宣告
  ``when`` / ``require`` 的 pre-merge gate 規則。
* ``commit_msg_trigger`` —— 從 commit message 解析
  ``[skip ci]`` / ``[ci e2e]`` / ``[ci shard=3/8]`` / ``Closes #123``。
* ``flakiness_graveyard`` —— Quarantine / revive / bury ledger,
  附 TTL 用於塵封的 flaky test。
* ``test_blame_owner`` —— CODEOWNERS + git-blame + HEAD + 預設
  的 test owner 解析鏈。
* ``test_dup_dry`` —— 結構式 action JSON 重複 + 共同前綴偵測
  (擷取 helper 機會)。
* ``snapshot_diff_approval`` —— Baseline / pending / rejected
  snapshot 註冊 + approval workflow。
* ``failure_cluster_dbscan`` —— 失敗訊息 tokeniser + DBSCAN 根因
  分群(純 Python,不依賴 sklearn)。
* ``test_naming_lint`` —— ``should_when`` / ``given_when_then`` /
  ``camel_subject`` 命名規範 linter。

i18n / a11y(續)
=================

* ``rtl_layout_verify`` —— RTL 方向 + logical property
  (``margin-inline-start``)+ bidi-isolation 稽核。
* ``dst_boundary_test`` —— 日光節約時間 spring-forward / fall-back
  缺口與重疊偵測 + scheduled-fire 模型。
* ``number_currency_locale`` —— 數字 / 貨幣 / 日期的 locale-format
  斷言 helper(含印度 lakh 分隔)。
* ``wcag22_touch_target`` —— WCAG 2.2 SC 2.5.8 觸控目標尺寸稽核
  含 spacing-circle 例外。

新興科技裝置 API
================

* ``webgpu_pixel_verify`` —— WebGPU canvas 像素讀回 + 平均 /
  純色 / tile-diff 斷言。
* ``webhid_mock`` —— WebHID 裝置 shim + input / output report 擷取。
* ``webusb_mock`` —— WebUSB 裝置 shim + control / bulk transfer
  擷取。
* ``webserial_mock`` —— Web Serial UART shim + line-write 擷取。
* ``webcodecs_assert`` —— WebCodecs chunk codec / 解析度 /
  keyframe 間距 / framerate 斷言。
* ``speech_api_assert`` —— ``SpeechSynthesis`` / ``SpeechRecognition``
  mock + utterance / 語言 / 音量 斷言。

延伸閱讀
========

* :doc:`../quality_security/quality_security_doc` —— 原始的品質 /
  安全 helper(linter、secret scanner、security header、Lighthouse、
  perf budget 等)。
* 中文版尚未提供 API reference,可參考英文版
  ``docs/source/Eng/doc/api_reference/`` 的內容。

* ``CLAUDE.md`` 在 repo 根目錄 —— 完整的 utils 樹,每個模組一行
  描述。
