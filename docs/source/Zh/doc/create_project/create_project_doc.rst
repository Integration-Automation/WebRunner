建立專案
========

概述
----

WebRunner 可以產生快速啟動的專案結構，包含範例 JSON 關鍵字檔案和 Python 執行器腳本。

用法
----

.. code-block:: python

    from je_web_runner import create_project_dir

    # 在當前工作目錄建立
    create_project_dir()

    # 在指定路徑建立
    create_project_dir(project_path="./my_project")

    # 自訂父目錄名稱
    create_project_dir(project_path="./my_project", parent_name="MyTest")

命令列方式
----------

.. code-block:: bash

    python -m je_web_runner --create_project ./my_project

產生的結構
----------

.. code-block:: text

    my_project/WebRunner/
    ├── keyword/
    │   ├── keyword1.json          # 範例動作檔案（成功案例）
    │   ├── keyword2.json          # 範例動作檔案（成功案例）
    │   └── bad_keyword_1.json     # 範例動作檔案（失敗案例）
    └── executor/
        ├── executor_one_file.py   # 執行單一 JSON 檔案
        ├── executor_folder.py     # 執行資料夾中所有 JSON 檔案
        └── executor_bad_file.py   # 執行失敗案例檔案

參數
----

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - 參數
     - 預設值
     - 說明
   * - ``project_path``
     - 當前工作目錄
     - 專案建立路徑
   * - ``parent_name``
     - ``"WebRunner"``
     - 頂層專案目錄名稱
