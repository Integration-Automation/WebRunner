# WebRunner

<p align="center">
  <strong>基於 Selenium 的跨平台網頁自動化框架</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/je-web-runner/"><img src="https://img.shields.io/pypi/v/je_web_runner" alt="PyPI 版本"></a>
  <a href="https://pypi.org/project/je-web-runner/"><img src="https://img.shields.io/pypi/pyversions/je_web_runner" alt="Python 版本"></a>
  <a href="https://github.com/Intergration-Automation-Testing/WebRunner/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Intergration-Automation-Testing/WebRunner" alt="授權"></a>
  <a href="https://webrunner.readthedocs.io/en/latest/"><img src="https://img.shields.io/badge/docs-readthedocs-blue" alt="文件"></a>
</p>

<p align="center">
  <a href="../README.md">English</a> |
  <a href="README_zh-CN.md">简体中文</a>
</p>

---

WebRunner（`je_web_runner`）是一款跨平台網頁自動化框架，旨在簡化瀏覽器自動化操作。它支援多種瀏覽器、並行執行、自動驅動程式管理，並能產生詳細的測試報告。基於 Selenium 構建並提供額外的抽象層，WebRunner 協助開發者輕鬆撰寫、執行及管理自動化腳本。

## 目錄

- [核心功能](#核心功能)
- [安裝](#安裝)
- [系統需求](#系統需求)
- [快速開始](#快速開始)
- [架構概覽](#架構概覽)
- [核心元件](#核心元件)
  - [WebDriver 管理器](#webdriver-管理器)
  - [WebDriver 包裝器](#webdriver-包裝器)
  - [網頁元素包裝器](#網頁元素包裝器)
  - [測試物件](#測試物件)
- [動作執行器](#動作執行器)
  - [動作格式](#動作格式)
  - [可用指令](#可用指令)
  - [從 JSON 檔案執行](#從-json-檔案執行)
- [報告產生](#報告產生)
- [遠端自動化（Socket 伺服器）](#遠端自動化socket-伺服器)
- [回呼執行器](#回呼執行器)
- [套件管理器](#套件管理器)
- [專案範本](#專案範本)
- [命令列介面](#命令列介面)
- [WebDriver 選項設定](#webdriver-選項設定)
- [測試紀錄](#測試紀錄)
- [例外處理](#例外處理)
- [日誌記錄](#日誌記錄)
- [支援的瀏覽器](#支援的瀏覽器)
- [支援的平台](#支援的平台)
- [授權條款](#授權條款)

## 核心功能

- **多瀏覽器支援** — Chrome、Chromium、Firefox、Edge、IE、Safari
- **自動 WebDriver 管理** — 透過 `webdriver-manager` 自動下載與設定
- **並行執行** — 同時管理多個瀏覽器實例
- **動作執行器** — 以 JSON 動作列表定義自動化腳本
- **報告產生** — HTML、JSON 及 XML 格式的測試報告，含成功/失敗標示
- **遠端自動化** — TCP Socket 伺服器，支援遠端指令執行
- **回呼系統** — 事件驅動的自動化回呼機制
- **動態擴充** — 於執行期間將外部 Python 套件載入執行器
- **專案範本** — 快速建立專案結構
- **跨平台** — Windows、macOS、Ubuntu、Raspberry Pi
- **命令列介面** — 從命令列直接執行自動化腳本
- **螢幕截圖** — 自動擷取螢幕截圖（PNG、Base64）
- **全面的元素互動** — 定位、點擊、輸入、拖放等操作

## 安裝

**穩定版：**

```bash
pip install je_web_runner
```

**開發版：**

```bash
pip install je_web_runner_dev
```

## 系統需求

- Python **3.10** 或更高版本
- 相依套件：`selenium>=4.0.0`、`requests`、`python-dotenv`、`webdriver-manager`

## 快速開始

### 範例 1：直接使用 API

```python
from je_web_runner import TestObject
from je_web_runner import get_webdriver_manager
from je_web_runner import web_element_wrapper

# 建立 WebDriver 管理器（使用 Chrome）
manager = get_webdriver_manager("chrome")

# 前往指定網址
manager.webdriver_wrapper.to_url("https://www.google.com")

# 設定隱式等待
manager.webdriver_wrapper.implicitly_wait(2)

# 建立測試物件，以 name 屬性定位搜尋框
search_box = TestObject("q", "name")

# 尋找元素
manager.webdriver_wrapper.find_element(search_box)

# 點擊並輸入文字
web_element_wrapper.click_element()
web_element_wrapper.input_to_element("WebRunner 自動化")

# 關閉瀏覽器
manager.quit()
```

### 範例 2：JSON 動作列表

```python
from je_web_runner import execute_action

actions = [
    ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
    ["WR_to_url", {"url": "https://www.google.com"}],
    ["WR_implicitly_wait", {"time_to_wait": 2}],
    ["WR_SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
    ["WR_find_element", {"element_name": "q"}],
    ["WR_click_element"],
    ["WR_input_to_element", {"input_value": "WebRunner 自動化"}],
    ["WR_quit"]
]

result = execute_action(actions)
```

## 架構概覽

```
je_web_runner/
├── __init__.py              # 公開 API 匯出
├── __main__.py              # 命令列進入點
├── element/
│   └── web_element_wrapper.py   # 網頁元素互動包裝器
├── manager/
│   └── webrunner_manager.py     # 多驅動程式管理
├── webdriver/
│   ├── webdriver_wrapper.py     # 核心 WebDriver 包裝器
│   └── webdriver_with_options.py # 瀏覽器選項設定
└── utils/
    ├── callback/                # 回呼函式執行器
    ├── exception/               # 自訂例外類別
    ├── executor/                # 動作執行引擎
    ├── file_process/            # 檔案工具
    ├── generate_report/         # HTML/JSON/XML 報告產生器
    ├── json/                    # JSON 檔案操作
    ├── logging/                 # 日誌設定
    ├── package_manager/         # 動態套件載入
    ├── project/                 # 專案範本產生器
    ├── selenium_utils_wrapper/  # Selenium 工具（Keys、Capabilities）
    ├── socket_server/           # TCP Socket 伺服器（遠端控制）
    ├── test_object/             # 測試物件與紀錄類別
    ├── test_record/             # 動作紀錄
    └── xml/                     # XML 工具
```

## 核心元件

### WebDriver 管理器

`WebdriverManager` 管理多個 WebDriver 實例，支援並行瀏覽器自動化。

```python
from je_web_runner import get_webdriver_manager

# 建立管理器（使用 Chrome）
manager = get_webdriver_manager("chrome")

# 新增另一個瀏覽器實例
manager.new_driver("firefox")

# 切換瀏覽器實例
manager.change_webdriver(0)  # 切換至 Chrome
manager.change_webdriver(1)  # 切換至 Firefox

# 關閉特定驅動程式
manager.close_choose_webdriver(1)  # 關閉 Firefox

# 關閉所有驅動程式
manager.quit()
```

### WebDriver 包裝器

`WebDriverWrapper` 是核心元件，包裝了 Selenium WebDriver 並提供全面的方法。

#### 導航

```python
wrapper = manager.webdriver_wrapper

wrapper.to_url("https://example.com")
wrapper.forward()
wrapper.back()
wrapper.refresh()
```

#### 元素定位

```python
from je_web_runner import TestObject

# 定位策略：id、name、xpath、css selector、class name、tag name、link text、partial link text
element = TestObject("search-input", "id")
wrapper.find_element(element)      # 尋找單一元素
wrapper.find_elements(element)     # 尋找多個元素
```

#### 等待方法

```python
wrapper.implicitly_wait(5)                    # 隱式等待（秒）
wrapper.explict_wait(10, method=some_func)    # 顯式等待（WebDriverWait）
wrapper.set_script_timeout(30)                # 非同步腳本逾時
wrapper.set_page_load_timeout(60)             # 頁面載入逾時
```

#### 滑鼠與鍵盤操作

```python
wrapper.left_click()                          # 左鍵點擊
wrapper.right_click()                         # 右鍵點擊
wrapper.left_double_click()                   # 雙擊
wrapper.left_click_and_hold()                 # 按住不放
wrapper.release()                             # 釋放
wrapper.drag_and_drop(source, target)         # 拖放
wrapper.drag_and_drop_offset(element, x=100, y=50)  # 偏移拖放
wrapper.move_to_element(element)              # 滑鼠懸停
wrapper.move_by_offset(100, 200)              # 偏移移動
wrapper.press_key(keycode)                    # 按下按鍵
wrapper.release_key(keycode)                  # 釋放按鍵
wrapper.send_keys("文字")                     # 發送按鍵
wrapper.send_keys_to_element(element, "文字") # 對元素發送按鍵
wrapper.perform()                             # 執行佇列中的動作
wrapper.reset_actions()                       # 清除動作佇列
wrapper.pause(2)                              # 暫停
```

#### Cookie 管理

```python
wrapper.get_cookies()                          # 取得所有 Cookie
wrapper.get_cookie("session_id")               # 取得特定 Cookie
wrapper.add_cookie({"name": "key", "value": "val"})
wrapper.delete_cookie("session_id")
wrapper.delete_all_cookies()
```

#### JavaScript 執行

```python
wrapper.execute_script("document.title")
wrapper.execute_async_script("arguments[0]('done')", callback)
```

#### 視窗管理

```python
wrapper.maximize_window()                      # 最大化
wrapper.minimize_window()                      # 最小化
wrapper.fullscreen_window()                    # 全螢幕
wrapper.set_window_size(1920, 1080)           # 設定大小
wrapper.set_window_position(0, 0)             # 設定位置
wrapper.get_window_position()                  # 取得位置
wrapper.get_window_rect()                      # 取得矩形資訊
wrapper.set_window_rect(x=0, y=0, width=1920, height=1080)
```

#### 螢幕截圖與捲動

```python
wrapper.get_screenshot_as_png()       # 回傳 bytes
wrapper.get_screenshot_as_base64()    # 回傳 base64 字串
wrapper.scroll(0, 500)               # 捲動頁面
```

#### Frame / 視窗 / Alert 切換

```python
wrapper.switch("frame", "frame_name")
wrapper.switch("window", "window_handle")
wrapper.switch("default_content")
```

#### 瀏覽器日誌

```python
wrapper.get_log("browser")
```

### 網頁元素包裝器

`WebElementWrapper` 提供與已定位元素互動的方法。

```python
from je_web_runner import web_element_wrapper

web_element_wrapper.click_element()                # 點擊
web_element_wrapper.input_to_element("Hello World") # 輸入
web_element_wrapper.clear()                        # 清除
web_element_wrapper.submit()                       # 提交

# 檢查屬性
web_element_wrapper.get_attribute("href")
web_element_wrapper.get_property("checked")
web_element_wrapper.get_dom_attribute("data-id")
web_element_wrapper.is_displayed()                 # 是否可見
web_element_wrapper.is_enabled()                   # 是否啟用
web_element_wrapper.is_selected()                  # 是否選取
web_element_wrapper.value_of_css_property("color") # CSS 屬性值

# 下拉選單
select = web_element_wrapper.get_select()

# 元素截圖
web_element_wrapper.screenshot("element.png")

# 從列表切換活動元素
web_element_wrapper.change_web_element(2)

# 驗證元素屬性
web_element_wrapper.check_current_web_element({"tag_name": "input"})
```

### 測試物件

`TestObject` 封裝元素定位資訊，可重複使用。

```python
from je_web_runner import TestObject, create_test_object, get_test_object_type_list

# 兩種建立方式
obj1 = TestObject("search", "name")
obj2 = create_test_object("id", "submit-btn")

# 檢視可用的定位類型
print(get_test_object_type_list())
# ['ID', 'NAME', 'XPATH', 'CSS_SELECTOR', 'CLASS_NAME', 'TAG_NAME', 'LINK_TEXT', 'PARTIAL_LINK_TEXT']
```

## 動作執行器

動作執行器是一個強大的引擎，將指令字串對應到可呼叫的函式。它允許您以 JSON 動作列表定義自動化腳本。

### 動作格式

每個動作是一個列表，包含指令名稱和可選參數：

```python
["指令名稱"]                        # 無參數
["指令名稱", {"key": "value"}]      # 關鍵字參數
["指令名稱", [arg1, arg2]]          # 位置參數
```

### 可用指令

| 類別 | 指令 |
|------|------|
| **管理器** | `WR_get_webdriver_manager`、`WR_change_index_of_webdriver`、`WR_quit` |
| **導航** | `WR_to_url`、`WR_forward`、`WR_back`、`WR_refresh` |
| **元素** | `WR_find_element`、`WR_find_elements`、`WR_find_element_with_test_object_record`、`WR_find_elements_with_test_object_record` |
| **等待** | `WR_implicitly_wait`、`WR_explict_wait`、`WR_set_script_timeout`、`WR_set_page_load_timeout` |
| **點擊** | `WR_left_click`、`WR_right_click`、`WR_left_double_click`、`WR_left_click_and_hold`、`WR_release` |
| **拖放** | `WR_drag_and_drop`、`WR_drag_and_drop_offset`、`WR_drag_and_drop_with_test_object`、`WR_drag_and_drop_offset_with_test_object` |
| **懸停** | `WR_move_to_element`、`WR_move_to_element_with_offset`、`WR_move_by_offset` |
| **鍵盤** | `WR_press_key`、`WR_release_key`、`WR_send_keys`、`WR_send_keys_to_element` |
| **動作鏈** | `WR_perform`、`WR_reset_actions`、`WR_pause` |
| **Cookie** | `WR_get_cookies`、`WR_get_cookie`、`WR_add_cookie`、`WR_delete_cookie`、`WR_delete_all_cookies` |
| **JavaScript** | `WR_execute_script`、`WR_execute_async_script` |
| **視窗** | `WR_maximize_window`、`WR_minimize_window`、`WR_fullscreen_window`、`WR_set_window_size`、`WR_set_window_position`、`WR_set_window_rect` |
| **截圖** | `WR_get_screenshot_as_png`、`WR_get_screenshot_as_base64` |
| **元素操作** | `WR_click_element`、`WR_input_to_element`、`WR_element_clear`、`WR_element_submit`、`WR_element_get_attribute`、`WR_element_is_displayed`、`WR_element_is_enabled`、`WR_element_is_selected` |
| **測試物件** | `WR_SaveTestObject`、`WR_CleanTestObject` |
| **報告** | `WR_generate_html_report`、`WR_generate_json_report`、`WR_generate_xml_report` |
| **套件** | `WR_add_package_to_executor` |
| **巢狀執行** | `WR_execute_action`、`WR_execute_files` |

### 從 JSON 檔案執行

```python
from je_web_runner import execute_files

# 從 JSON 檔案執行動作
results = execute_files(["actions1.json", "actions2.json"])
```

JSON 檔案格式：

```json
[
    ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
    ["WR_to_url", {"url": "https://example.com"}],
    ["WR_quit"]
]
```

### 新增自訂指令

```python
from je_web_runner import add_command_to_executor

def my_custom_function(param1, param2):
    print(f"自訂：{param1}、{param2}")

add_command_to_executor({"my_command": my_custom_function})
```

## 報告產生

WebRunner 可自動記錄所有動作，並以三種格式產生報告。

### 啟用紀錄

```python
from je_web_runner import test_record_instance

test_record_instance.set_record_enable(True)
```

### HTML 報告

```python
from je_web_runner import generate_html, generate_html_report

# 產生 HTML 字串
html_content = generate_html()

# 儲存至檔案（建立 test_results.html）
generate_html_report("test_results")
```

HTML 報告包含顏色標記的表格：成功為**青色**，失敗為**紅色**。每列顯示函式名稱、參數、時間戳記及例外資訊（如有）。

### JSON 報告

```python
from je_web_runner import generate_json, generate_json_report

# 產生字典
success_dict, failure_dict = generate_json()

# 儲存至檔案（建立 test_results_success.json 和 test_results_failure.json）
generate_json_report("test_results")
```

### XML 報告

```python
from je_web_runner import generate_xml, generate_xml_report

# 產生 XML 字串
success_xml, failure_xml = generate_xml()

# 儲存至檔案（建立 test_results_success.xml 和 test_results_failure.xml）
generate_xml_report("test_results")
```

## 遠端自動化（Socket 伺服器）

WebRunner 內建多執行緒 TCP Socket 伺服器，支援遠端自動化控制。

### 啟動伺服器

```python
from je_web_runner import start_web_runner_socket_server

server = start_web_runner_socket_server(host="localhost", port=9941)
```

### 客戶端連線

```python
import socket
import json

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("localhost", 9941))

# 以 JSON 格式發送動作
actions = [
    ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
    ["WR_to_url", {"url": "https://example.com"}],
    ["WR_quit"]
]
sock.send(json.dumps(actions).encode("utf-8"))

# 接收結果（以 "Return_Data_Over_JE\n" 結尾）
response = sock.recv(4096).decode("utf-8")
print(response)

# 關閉伺服器
sock.send("quit_server".encode("utf-8"))
```

## 回呼執行器

執行自動化指令並在完成後觸發回呼函式。

```python
from je_web_runner import callback_executor

def on_complete():
    print("導航完成！")

callback_executor.callback_function(
    trigger_function_name="WR_to_url",
    callback_function=on_complete,
    url="https://example.com"
)
```

附帶參數：

```python
def on_element_found(result=None):
    print(f"元素已找到：{result}")

callback_executor.callback_function(
    trigger_function_name="WR_find_element",
    callback_function=on_element_found,
    callback_function_param={"result": "search_box"},
    callback_param_method="kwargs",
    element_name="search_box"
)
```

## 套件管理器

於執行期間動態載入外部 Python 套件至執行器。

```python
from je_web_runner import execute_action

actions = [
    # 載入 'time' 套件
    ["WR_add_package_to_executor", {"package": "time"}],
    # 現在可以使用 time.sleep
    ["time_sleep", [2]]
]

execute_action(actions)
```

## 專案範本

快速建立專案結構及範例檔案。

```python
from je_web_runner import create_project_dir

create_project_dir(project_path="./my_project", parent_name="WebRunner")
```

產生的結構：

```
my_project/WebRunner/
├── keyword/
│   ├── keyword1.json
│   ├── keyword2.json
│   └── bad_keyword_1.json
└── executor/
    ├── executor_one_file.py
    ├── executor_folder.py
    └── executor_bad_file.py
```

## 命令列介面

WebRunner 可直接從命令列執行。

```bash
# 執行單一 JSON 動作檔案
python -m je_web_runner -e actions.json

# 執行目錄中所有 JSON 檔案
python -m je_web_runner -d ./actions/

# 直接執行 JSON 字串
python -m je_web_runner --execute_str '[["WR_get_webdriver_manager", {"webdriver_name": "chrome"}], ["WR_quit"]]'
```

## WebDriver 選項設定

於啟動前設定瀏覽器選項。

```python
from je_web_runner import set_webdriver_options_argument, get_webdriver_manager

# 設定瀏覽器參數（例如：無頭模式）
options = set_webdriver_options_argument("chrome", [
    "--headless",
    "--disable-gpu",
    "--no-sandbox",
    "--window-size=1920,1080"
])

# 以選項啟動
manager = get_webdriver_manager("chrome", options=["--headless", "--disable-gpu"])
```

### DesiredCapabilities

```python
from je_web_runner import get_desired_capabilities, get_desired_capabilities_keys

# 檢視可用的功能
keys = get_desired_capabilities_keys()

# 取得瀏覽器的功能
caps = get_desired_capabilities("CHROME")
```

## 測試紀錄

所有 WebRunner 動作會自動記錄，用於稽核追蹤及報告產生。

```python
from je_web_runner import test_record_instance

# 啟用紀錄
test_record_instance.set_record_enable(True)

# ... 執行自動化操作 ...

# 存取紀錄
records = test_record_instance.test_record_list

# 每筆紀錄包含：
# {
#     "function_name": "to_url",
#     "local_param": {"url": "https://example.com"},
#     "time": "2025-01-01 12:00:00",
#     "program_exception": "None"
# }

# 清除紀錄
test_record_instance.clean_record()
```

## 例外處理

WebRunner 提供完整的自訂例外階層：

| 例外 | 說明 |
|------|------|
| `WebRunnerException` | 基礎例外 |
| `WebRunnerWebDriverNotFoundException` | 找不到 WebDriver |
| `WebRunnerOptionsWrongTypeException` | 選項類型錯誤 |
| `WebRunnerArgumentWrongTypeException` | 參數類型錯誤 |
| `WebRunnerWebDriverIsNoneException` | WebDriver 為 None |
| `WebRunnerExecuteException` | 執行錯誤 |
| `WebRunnerJsonException` | JSON 處理錯誤 |
| `WebRunnerGenerateJsonReportException` | JSON 報告產生錯誤 |
| `WebRunnerAssertException` | 斷言失敗 |
| `WebRunnerHTMLException` | HTML 報告錯誤 |
| `WebRunnerAddCommandException` | 指令註冊錯誤 |
| `XMLException` / `XMLTypeException` | XML 處理錯誤 |
| `CallbackExecutorException` | 回呼執行錯誤 |

## 日誌記錄

WebRunner 使用旋轉式檔案處理器記錄日誌。

- **日誌檔案：** `WEBRunner.log`
- **日誌等級：** WARNING 及以上
- **檔案大小上限：** 1 GB
- **格式：** `%(asctime)s | %(name)s | %(levelname)s | %(message)s`

## 支援的瀏覽器

| 瀏覽器 | 識別碼 |
|--------|--------|
| Google Chrome | `chrome` |
| Chromium | `chromium` |
| Mozilla Firefox | `firefox` |
| Microsoft Edge | `edge` |
| Internet Explorer | `ie` |
| Apple Safari | `safari` |

## 支援的平台

- Windows
- macOS
- Ubuntu / Linux
- Raspberry Pi

## 授權條款

本專案採用 [MIT 授權條款](../LICENSE)。

Copyright (c) 2021~2023 JE-Chen
