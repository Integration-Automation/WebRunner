==========
瀏覽器底層
==========

* 原生 CDP 直通
* localStorage / sessionStorage / IndexedDB
* Service Worker / cache
* Console + 網路事件擷取
* Shadow DOM piercing
* 多層 iframe
* 檔案上傳 / 下載
* 瀏覽器擴充功能載入

裝置 / 區域
===========

* ``device_emulation`` — iPhone / Pixel / iPad / Desktop 預設
* ``geo_locale`` — geolocation / timezone / locale 一次設定
* ``multi_tab.TabChoreographer`` — 多分頁腳本連動
* ``webauthn.enable_virtual_authenticator`` — passkey / FIDO2 模擬

Storybook / Shadow DOM
======================

* ``storybook.discover_stories`` + ``plan_actions_for_stories`` — 走訪
  Storybook stories 自動跑 axe + screenshot
* ``storybook.visual_snapshots.capture_story_snapshots`` — 走訪 stories
  截圖、可選擇與 baseline byte-level 比對
* ``dom_traversal.shadow_pierce.find_first`` — 遞迴穿透 open shadow
  root 找元件，Selenium 與 Playwright 通吃

CDP tap / Cross-browser / State diff
====================================

* ``cdp_tap.CdpRecorder`` / ``CdpReplayer`` — 把 ``execute_cdp_cmd``
  的呼叫全錄成 ndjson、之後可離線 replay
* ``cross_browser.diff_runs`` — 同 action JSON 跑 Chromium / Firefox /
  WebKit 後比對 title / DOM / console / 網路 / 截圖差異
* ``state_diff.capture_state`` + ``diff_states`` — 比對測試前後的
  cookies / localStorage / sessionStorage 變化
