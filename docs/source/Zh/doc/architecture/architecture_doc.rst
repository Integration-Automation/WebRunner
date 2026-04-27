====
架構
====

系統概觀
========

.. mermaid::

   flowchart LR
     A1["Action JSON"] --> EXE["Executor"]
     A2["錄製器"] --> A1
     A3["LLM NL → 草稿"] --> A1
     EXE --> SEL["Selenium"]
     EXE --> PW["Playwright"]
     EXE --> APM["Appium"]
     EXE --> HTTP["HTTP API"]
     EXE --> DB["資料庫"]
     SEL --> REC["紀錄"]
     PW --> REC
     REC --> REP["報告"]
     REC --> OBS["可觀測"]
     REC --> NOT["通知"]

Action 生命週期
===============

.. mermaid::

   flowchart LR
     IN["[cmd, args, kwargs]"] --> VAL["驗證器"]
     VAL --> ENV["${ENV.X} / ${ROW.x}"]
     ENV --> SPAN["OTel span"]
     SPAN --> RETRY["重試策略"]
     RETRY --> GATE["Script 開關"]
     GATE --> DISP["event_dict[cmd]"]
     DISP --> RECORD["records.append"]
     DISP -- 失敗 --> SHOT["自動截圖"]
