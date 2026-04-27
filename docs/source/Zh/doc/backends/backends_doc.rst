========
Backends
========

Selenium（預設）
================

原本的 ``WebDriverWrapper`` 與 ``WebElementWrapper``。所有沒有特定前綴的
命令都會走這條。

Playwright
==========

完整鏡像 Selenium 的命令面，前綴為 ``WR_pw_*``：

* lifecycle / 分頁 / 導覽
* find（含 ``TestObject`` 自動翻譯）與直接的 page-level 快捷
* 元素層 wrapper
* 行動裝置模擬、locale、時區、地理位置、權限、clock
* HAR 錄製、route mock、console + 網路事件擷取
* 透過 CDP 的網路節流預設集

opt-in 設計：既有腳本可繼續跑在 Selenium 上。

雲端 Grid
=========

對應 BrowserStack / Sauce Labs / LambdaTest 的 helper。

Appium（行動）
==============

``start_appium_session`` 建立 Appium driver 並掛在 Selenium wrapper 上，既
有 ``WR_*`` 命令直接適用 mobile session。

``appium_integration.gestures`` 提供高階手勢：``swipe`` / ``scroll`` /
``long_press`` / ``pinch`` / ``double_tap``，優先用 ``mobile:`` 擴充
否則退回 W3C Actions。
