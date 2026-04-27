==========
品質與安全
==========

* Action linter
* Migration helper（舊命令 → 新別名）
* 寫死密碼掃描
* HTTP 安全 headers 稽核
* axe-core 可訪問性
* Lighthouse 跑分
* Core Web Vitals
* Visual regression
* 文字 / DOM snapshot
* 網路節流預設集
* Arbitrary-script 開關

安全測試
========

* ``header_tampering.HeaderTampering`` — 改 cookie/referer/origin
* ``license_scanner`` — SPDX / 已知授權字樣偵測
* ``cookie_consent.ConsentDismisser`` — 自動關閉 GDPR 彈窗

PII / Visual review
===================

* ``pii_scanner.scan_text`` — email / 電話 / Luhn 驗證信用卡 / SSN /
  ROC 身分證號 / IPv4，``assert_no_pii`` 與 ``redact_text`` 配套
* ``visual_review.VisualReviewServer`` — 本機 web UI side-by-side 顯示
  baseline / current，一鍵 accept

Form auto-fill / A11y diff
==========================

* ``form_autofill.plan_fill_actions(fields, fixture)`` — 自動推斷欄位
  用途並產出 ``WR_save_test_object`` + ``WR_element_input`` 序列
* ``accessibility.a11y_diff.diff_violations`` — 比較兩次 axe-core 結果
  分出 added / resolved / persisting；``assert_no_regressions`` 為
  CI 把關
