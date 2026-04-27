============
Architecture
============

System overview
===============

.. mermaid::

   flowchart LR
     A1["Action JSON"] --> EXE["Executor"]
     A2["Recorder"] --> A1
     A3["LLM NL → draft"] --> A1
     EXE --> SEL["Selenium"]
     EXE --> PW["Playwright"]
     EXE --> APM["Appium"]
     EXE --> HTTP["HTTP API"]
     EXE --> DB["Database"]
     SEL --> REC["Records"]
     PW --> REC
     REC --> REP["Reports"]
     REC --> OBS["Observability"]
     REC --> NOT["Notifiers"]

Action lifecycle
================

.. mermaid::

   flowchart LR
     IN["[cmd, args, kwargs]"] --> VAL["Validator"]
     VAL --> ENV["${ENV.X} / ${ROW.x}"]
     ENV --> SPAN["OTel span"]
     SPAN --> RETRY["Retry policy"]
     RETRY --> GATE["Script gate"]
     GATE --> DISP["event_dict[cmd]"]
     DISP --> RECORD["records.append"]
     DISP -- failure --> SHOT["Auto screenshot"]
