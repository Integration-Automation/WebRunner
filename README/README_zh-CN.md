# WebRunner

<p align="center">
  <strong>基于 Selenium 的跨平台网页自动化框架</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/je-web-runner/"><img src="https://img.shields.io/pypi/v/je_web_runner" alt="PyPI 版本"></a>
  <a href="https://pypi.org/project/je-web-runner/"><img src="https://img.shields.io/pypi/pyversions/je_web_runner" alt="Python 版本"></a>
  <a href="https://github.com/Intergration-Automation-Testing/WebRunner/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Intergration-Automation-Testing/WebRunner" alt="许可证"></a>
  <a href="https://webrunner.readthedocs.io/en/latest/"><img src="https://img.shields.io/badge/docs-readthedocs-blue" alt="文档"></a>
</p>

<p align="center">
  <a href="../README.md">English</a> |
  <a href="README_zh-TW.md">繁體中文</a>
</p>

---

WebRunner（`je_web_runner`）是一款跨平台网页自动化框架，旨在简化浏览器自动化操作。它支持多种浏览器、并行执行、自动驱动程序管理，并能生成详细的测试报告。基于 Selenium 构建并提供额外的抽象层，WebRunner 帮助开发者轻松编写、执行及管理自动化脚本。

## 目录

- [核心功能](#核心功能)
- [安装](#安装)
- [系统要求](#系统要求)
- [快速开始](#快速开始)
- [架构概览](#架构概览)
- [核心组件](#核心组件)
  - [WebDriver 管理器](#webdriver-管理器)
  - [WebDriver 包装器](#webdriver-包装器)
  - [网页元素包装器](#网页元素包装器)
  - [测试对象](#测试对象)
- [动作执行器](#动作执行器)
  - [动作格式](#动作格式)
  - [可用指令](#可用指令)
  - [从 JSON 文件执行](#从-json-文件执行)
- [报告生成](#报告生成)
- [远程自动化（Socket 服务器）](#远程自动化socket-服务器)
- [回调执行器](#回调执行器)
- [包管理器](#包管理器)
- [项目模板](#项目模板)
- [命令行接口](#命令行接口)
- [WebDriver 选项配置](#webdriver-选项配置)
- [测试记录](#测试记录)
- [异常处理](#异常处理)
- [日志记录](#日志记录)
- [支持的浏览器](#支持的浏览器)
- [支持的平台](#支持的平台)
- [进阶模块](#进阶模块)
- [许可证](#许可证)

## 核心功能

- **多浏览器支持** — Chrome、Chromium、Firefox、Edge、IE、Safari
- **自动 WebDriver 管理** — 通过 `webdriver-manager` 自动下载与配置
- **并行执行** — 同时管理多个浏览器实例
- **动作执行器** — 以 JSON 动作列表定义自动化脚本
- **报告生成** — HTML、JSON 及 XML 格式的测试报告，含成功/失败标记
- **远程自动化** — TCP Socket 服务器，支持远程命令执行
- **回调系统** — 事件驱动的自动化回调机制
- **动态扩展** — 在运行时将外部 Python 包加载到执行器
- **项目模板** — 快速创建项目结构
- **跨平台** — Windows、macOS、Ubuntu、Raspberry Pi
- **命令行接口** — 从命令行直接执行自动化脚本
- **截图** — 自动捕获截图（PNG、Base64）
- **全面的元素交互** — 定位、点击、输入、拖放等操作

## 安装

**稳定版：**

```bash
pip install je_web_runner
```

**开发版：**

```bash
pip install je_web_runner_dev
```

## 系统要求

- Python **3.10** 或更高版本
- 依赖包：`selenium>=4.0.0`、`requests`、`python-dotenv`、`webdriver-manager`

## 快速开始

### 示例 1：直接使用 API

```python
from je_web_runner import TestObject
from je_web_runner import get_webdriver_manager
from je_web_runner import web_element_wrapper

# 创建 WebDriver 管理器（使用 Chrome）
manager = get_webdriver_manager("chrome")

# 导航到指定网址
manager.webdriver_wrapper.to_url("https://www.google.com")

# 设置隐式等待
manager.webdriver_wrapper.implicitly_wait(2)

# 创建测试对象，以 name 属性定位搜索框
search_box = TestObject("q", "name")

# 查找元素
manager.webdriver_wrapper.find_element(search_box)

# 点击并输入文字
web_element_wrapper.click_element()
web_element_wrapper.input_to_element("WebRunner 自动化")

# 关闭浏览器
manager.quit()
```

### 示例 2：JSON 动作列表

```python
from je_web_runner import execute_action

actions = [
    ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
    ["WR_to_url", {"url": "https://www.google.com"}],
    ["WR_implicitly_wait", {"time_to_wait": 2}],
    ["WR_SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
    ["WR_find_element", {"element_name": "q"}],
    ["WR_click_element"],
    ["WR_input_to_element", {"input_value": "WebRunner 自动化"}],
    ["WR_quit"]
]

result = execute_action(actions)
```

## 架构概览

```
je_web_runner/
├── __init__.py              # 公开 API 导出
├── __main__.py              # 命令行入口点
├── element/
│   └── web_element_wrapper.py   # 网页元素交互包装器
├── manager/
│   └── webrunner_manager.py     # 多驱动程序管理
├── webdriver/
│   ├── webdriver_wrapper.py     # 核心 WebDriver 包装器
│   └── webdriver_with_options.py # 浏览器选项配置
└── utils/
    ├── callback/                # 回调函数执行器
    ├── exception/               # 自定义异常类
    ├── executor/                # 动作执行引擎
    ├── file_process/            # 文件工具
    ├── generate_report/         # HTML/JSON/XML 报告生成器
    ├── json/                    # JSON 文件操作
    ├── logging/                 # 日志配置
    ├── package_manager/         # 动态包加载
    ├── project/                 # 项目模板生成器
    ├── selenium_utils_wrapper/  # Selenium 工具（Keys、Capabilities）
    ├── socket_server/           # TCP Socket 服务器（远程控制）
    ├── test_object/             # 测试对象与记录类
    ├── test_record/             # 动作记录
    └── xml/                     # XML 工具
```

## 核心组件

### WebDriver 管理器

`WebdriverManager` 管理多个 WebDriver 实例，支持并行浏览器自动化。

```python
from je_web_runner import get_webdriver_manager

# 创建管理器（使用 Chrome）
manager = get_webdriver_manager("chrome")

# 添加另一个浏览器实例
manager.new_driver("firefox")

# 切换浏览器实例
manager.change_webdriver(0)  # 切换到 Chrome
manager.change_webdriver(1)  # 切换到 Firefox

# 关闭特定驱动程序
manager.close_choose_webdriver(1)  # 关闭 Firefox

# 关闭所有驱动程序
manager.quit()
```

### WebDriver 包装器

`WebDriverWrapper` 是核心组件，包装了 Selenium WebDriver 并提供全面的方法。

#### 导航

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
wrapper.find_element(element)      # 查找单个元素
wrapper.find_elements(element)     # 查找多个元素
```

#### 等待方法

```python
wrapper.implicitly_wait(5)                    # 隐式等待（秒）
wrapper.explict_wait(10, method=some_func)    # 显式等待（WebDriverWait）
wrapper.set_script_timeout(30)                # 异步脚本超时
wrapper.set_page_load_timeout(60)             # 页面加载超时
```

#### 鼠标与键盘操作

```python
wrapper.left_click()                          # 左键点击
wrapper.right_click()                         # 右键点击
wrapper.left_double_click()                   # 双击
wrapper.left_click_and_hold()                 # 按住不放
wrapper.release()                             # 释放
wrapper.drag_and_drop(source, target)         # 拖放
wrapper.drag_and_drop_offset(element, x=100, y=50)  # 偏移拖放
wrapper.move_to_element(element)              # 鼠标悬停
wrapper.move_by_offset(100, 200)              # 偏移移动
wrapper.press_key(keycode)                    # 按下按键
wrapper.release_key(keycode)                  # 释放按键
wrapper.send_keys("文字")                     # 发送按键
wrapper.send_keys_to_element(element, "文字") # 向元素发送按键
wrapper.perform()                             # 执行队列中的动作
wrapper.reset_actions()                       # 清除动作队列
wrapper.pause(2)                              # 暂停
```

#### Cookie 管理

```python
wrapper.get_cookies()                          # 获取所有 Cookie
wrapper.get_cookie("session_id")               # 获取特定 Cookie
wrapper.add_cookie({"name": "key", "value": "val"})
wrapper.delete_cookie("session_id")
wrapper.delete_all_cookies()
```

#### JavaScript 执行

```python
wrapper.execute_script("document.title")
wrapper.execute_async_script("arguments[0]('done')", callback)
```

#### 窗口管理

```python
wrapper.maximize_window()                      # 最大化
wrapper.minimize_window()                      # 最小化
wrapper.fullscreen_window()                    # 全屏
wrapper.set_window_size(1920, 1080)           # 设置大小
wrapper.set_window_position(0, 0)             # 设置位置
wrapper.get_window_position()                  # 获取位置
wrapper.get_window_rect()                      # 获取矩形信息
wrapper.set_window_rect(x=0, y=0, width=1920, height=1080)
```

#### 截图与滚动

```python
wrapper.get_screenshot_as_png()       # 返回 bytes
wrapper.get_screenshot_as_base64()    # 返回 base64 字符串
wrapper.scroll(0, 500)               # 滚动页面
```

#### Frame / 窗口 / Alert 切换

```python
wrapper.switch("frame", "frame_name")
wrapper.switch("window", "window_handle")
wrapper.switch("default_content")
```

#### 浏览器日志

```python
wrapper.get_log("browser")
```

#### 高级 API（mixin 模块）

`WebDriverWrapper` 现以 mixin 组合，主题分散在
`je_web_runner/webdriver/_wrapper_mixins/`（cookies / actions / media /
navigation / scripting）；对外 import 不变。以下 API 同时都有对应的
`WR_*` 别名，可在 action JSON / MCP server 直接调用。

**启动参数（stealth / extension / BiDi）：**

```python
webdriver_wrapper_instance.set_driver(
    "chrome",
    options=["--disable-blink-features=AutomationControlled"],
    experimental_options={
        "excludeSwitches": ["enable-automation"],
        "useAutomationExtension": False,
    },
    extension_paths=["/path/to/extension.crx"],
    enable_bidi=True,                        # 开启 W3C BiDi 事件支持
)
# 连接到用户手动启动的 Chrome (--remote-debugging-port=9222)：
webdriver_wrapper_instance.attach_to_existing_browser("127.0.0.1:9222")
```

**CDP / Fetch / BiDi：**

```python
w = webdriver_wrapper_instance
w.execute_cdp_cmd("Page.bringToFront")
w.add_script_to_evaluate_on_new_document("/* stealth JS */")
w.set_timezone("Asia/Tokyo"); w.set_locale("ja-JP")
w.set_device_metrics(390, 844, device_scale_factor=3, mobile=True)
w.set_user_agent("Mozilla/5.0 (custom)")
w.set_extra_http_headers({"X-Run": "ci-123"})
w.set_geolocation(35.68, 139.69)
w.set_network_conditions(offline=False, latency=200,
                          download_throughput=50_000, upload_throughput=10_000)
w.block_urls(["*.doubleclick.net/*"]);    w.set_cache_disabled(True)
w.set_download_directory("./downloads")
w.clear_origin_storage("https://example.com")

# CDP Fetch 拦截（需配合 CDPEventListener 才能实际接收事件）：
w.enable_fetch_interception(patterns=["*/api/*"])
# 在 Fetch.requestPaused callback 中：
#   w.fulfill_request(rid, 200, body=b'{"ok":true}',
#                     response_headers={"Content-Type": "application/json"})
#   w.continue_request(rid, url=rewritten)
#   w.fail_request(rid, "AccessDenied")

# Selenium 4.16+ BiDi listener：
sub = w.add_console_listener(lambda msg: print(msg.text))
err = w.add_js_error_listener(lambda e: print("page exception:", e))
w.remove_console_listener(sub); w.remove_js_error_listener(err)
```

**页面 metadata / session 重用 / 截图：**

```python
w.get_current_url(); w.get_title(); w.get_page_source()
w.get_window_handles(); w.new_window("tab"); w.close_window()
w.switch_to_window_by_url("checkout"); w.switch_to_window_by_title("结账")
w.reload(ignore_cache=True)
w.save_cookies("./cookies.json"); w.load_cookies("./cookies.json")
w.save_full_page_screenshot("./shot.png")     # 全页截图（含可视范围外）
w.print_page("./page.pdf")
```

**独立模块（CDP 事件循环 / 跨浏览器 BiDi network / performance trace）：**

```python
from je_web_runner import CDPEventListener, record_trace, bidi_add_request_handler

# 后台 CDP WebSocket，命令 + 事件共享同一 session
with CDPEventListener.from_driver(driver) as listener:
    listener.on("Fetch.requestPaused", handle_paused)
    listener.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})

# 录制可载入 Chrome DevTools 的 performance trace
record_trace(driver, "perf.json",
             categories=["devtools.timeline", "loading"], duration=10.0)

# W3C BiDi network（跨浏览器，Selenium 4.16+，需 enable_bidi=True 启动）
sub_id = bidi_add_request_handler(driver, lambda req: print(req.url))
```

`CDPEventListener` 需 `pip install websocket-client`（lazy-import；缺包会抛 `CDPEventLoopError`）。

### 网页元素包装器

`WebElementWrapper` 提供与已定位元素交互的方法。

```python
from je_web_runner import web_element_wrapper

web_element_wrapper.click_element()                # 点击
web_element_wrapper.input_to_element("Hello World") # 输入
web_element_wrapper.clear()                        # 清除
web_element_wrapper.submit()                       # 提交

# 检查属性
web_element_wrapper.get_attribute("href")
web_element_wrapper.get_property("checked")
web_element_wrapper.get_dom_attribute("data-id")
web_element_wrapper.is_displayed()                 # 是否可见
web_element_wrapper.is_enabled()                   # 是否启用
web_element_wrapper.is_selected()                  # 是否选中
web_element_wrapper.value_of_css_property("color") # CSS 属性值

# 下拉选择框
select = web_element_wrapper.get_select()

# 元素截图
web_element_wrapper.screenshot("element.png")

# 从列表切换活动元素
web_element_wrapper.change_web_element(2)

# 验证元素属性
web_element_wrapper.check_current_web_element({"tag_name": "input"})
```

### 测试对象

`TestObject` 封装元素定位信息，可重复使用。

```python
from je_web_runner import TestObject, create_test_object, get_test_object_type_list

# 两种创建方式
obj1 = TestObject("search", "name")
obj2 = create_test_object("id", "submit-btn")

# 查看可用的定位类型
print(get_test_object_type_list())
# ['ID', 'NAME', 'XPATH', 'CSS_SELECTOR', 'CLASS_NAME', 'TAG_NAME', 'LINK_TEXT', 'PARTIAL_LINK_TEXT']
```

## 动作执行器

动作执行器是一个强大的引擎，将命令字符串映射到可调用的函数。它允许您以 JSON 动作列表定义自动化脚本。

### 动作格式

每个动作是一个列表，包含命令名称和可选参数：

```python
["命令名称"]                        # 无参数
["命令名称", {"key": "value"}]      # 关键字参数
["命令名称", [arg1, arg2]]          # 位置参数
```

### 可用指令

| 类别 | 指令 |
|------|------|
| **管理器** | `WR_get_webdriver_manager`、`WR_change_index_of_webdriver`、`WR_quit` |
| **导航** | `WR_to_url`、`WR_forward`、`WR_back`、`WR_refresh` |
| **元素** | `WR_find_element`、`WR_find_elements`、`WR_find_element_with_test_object_record`、`WR_find_elements_with_test_object_record` |
| **等待** | `WR_implicitly_wait`、`WR_explict_wait`、`WR_set_script_timeout`、`WR_set_page_load_timeout` |
| **点击** | `WR_left_click`、`WR_right_click`、`WR_left_double_click`、`WR_left_click_and_hold`、`WR_release` |
| **拖放** | `WR_drag_and_drop`、`WR_drag_and_drop_offset`、`WR_drag_and_drop_with_test_object`、`WR_drag_and_drop_offset_with_test_object` |
| **悬停** | `WR_move_to_element`、`WR_move_to_element_with_offset`、`WR_move_by_offset` |
| **键盘** | `WR_press_key`、`WR_release_key`、`WR_send_keys`、`WR_send_keys_to_element` |
| **动作链** | `WR_perform`、`WR_reset_actions`、`WR_pause` |
| **Cookie** | `WR_get_cookies`、`WR_get_cookie`、`WR_add_cookie`、`WR_delete_cookie`、`WR_delete_all_cookies` |
| **JavaScript** | `WR_execute_script`、`WR_execute_async_script` |
| **窗口** | `WR_maximize_window`、`WR_minimize_window`、`WR_fullscreen_window`、`WR_set_window_size`、`WR_set_window_position`、`WR_set_window_rect` |
| **截图** | `WR_get_screenshot_as_png`、`WR_get_screenshot_as_base64` |
| **元素操作** | `WR_click_element`、`WR_input_to_element`、`WR_element_clear`、`WR_element_submit`、`WR_element_get_attribute`、`WR_element_is_displayed`、`WR_element_is_enabled`、`WR_element_is_selected` |
| **测试对象** | `WR_SaveTestObject`、`WR_CleanTestObject` |
| **报告** | `WR_generate_html_report`、`WR_generate_json_report`、`WR_generate_xml_report` |
| **包** | `WR_add_package_to_executor` |
| **嵌套执行** | `WR_execute_action`、`WR_execute_files` |

### 从 JSON 文件执行

```python
from je_web_runner import execute_files

# 从 JSON 文件执行动作
results = execute_files(["actions1.json", "actions2.json"])
```

JSON 文件格式：

```json
[
    ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
    ["WR_to_url", {"url": "https://example.com"}],
    ["WR_quit"]
]
```

### 添加自定义命令

```python
from je_web_runner import add_command_to_executor

def my_custom_function(param1, param2):
    print(f"自定义：{param1}、{param2}")

add_command_to_executor({"my_command": my_custom_function})
```

## 报告生成

WebRunner 可自动记录所有动作，并以三种格式生成报告。

### 启用记录

```python
from je_web_runner import test_record_instance

test_record_instance.set_record_enable(True)
```

### HTML 报告

```python
from je_web_runner import generate_html, generate_html_report

# 生成 HTML 字符串
html_content = generate_html()

# 保存到文件（创建 test_results.html）
generate_html_report("test_results")
```

HTML 报告包含颜色标记的表格：成功为**青色**，失败为**红色**。每行显示函数名称、参数、时间戳及异常信息（如有）。

### JSON 报告

```python
from je_web_runner import generate_json, generate_json_report

# 生成字典
success_dict, failure_dict = generate_json()

# 保存到文件（创建 test_results_success.json 和 test_results_failure.json）
generate_json_report("test_results")
```

### XML 报告

```python
from je_web_runner import generate_xml, generate_xml_report

# 生成 XML 字符串
success_xml, failure_xml = generate_xml()

# 保存到文件（创建 test_results_success.xml 和 test_results_failure.xml）
generate_xml_report("test_results")
```

## 远程自动化（Socket 服务器）

WebRunner 内置多线程 TCP Socket 服务器，支持远程自动化控制。

### 启动服务器

```python
from je_web_runner import start_web_runner_socket_server

server = start_web_runner_socket_server(host="localhost", port=9941)
```

### 客户端连接

```python
import socket
import json

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("localhost", 9941))

# 以 JSON 格式发送动作
actions = [
    ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
    ["WR_to_url", {"url": "https://example.com"}],
    ["WR_quit"]
]
sock.send(json.dumps(actions).encode("utf-8"))

# 接收结果（以 "Return_Data_Over_JE\n" 结尾）
response = sock.recv(4096).decode("utf-8")
print(response)

# 关闭服务器
sock.send("quit_server".encode("utf-8"))
```

## 回调执行器

执行自动化命令并在完成后触发回调函数。

```python
from je_web_runner import callback_executor

def on_complete():
    print("导航完成！")

callback_executor.callback_function(
    trigger_function_name="WR_to_url",
    callback_function=on_complete,
    url="https://example.com"
)
```

带参数：

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

## 包管理器

在运行时动态加载外部 Python 包到执行器。

```python
from je_web_runner import execute_action

actions = [
    # 加载 'time' 包
    ["WR_add_package_to_executor", {"package": "time"}],
    # 现在可以使用 time.sleep
    ["time_sleep", [2]]
]

execute_action(actions)
```

## 项目模板

快速创建项目结构及示例文件。

```python
from je_web_runner import create_project_dir

create_project_dir(project_path="./my_project", parent_name="WebRunner")
```

生成的结构：

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

## 命令行接口

WebRunner 可直接从命令行执行。

```bash
# 执行单个 JSON 动作文件
python -m je_web_runner -e actions.json

# 执行目录中所有 JSON 文件
python -m je_web_runner -d ./actions/

# 直接执行 JSON 字符串
python -m je_web_runner --execute_str '[["WR_get_webdriver_manager", {"webdriver_name": "chrome"}], ["WR_quit"]]'
```

## WebDriver 选项配置

在启动前配置浏览器选项。

```python
from je_web_runner import set_webdriver_options_argument, get_webdriver_manager

# 设置浏览器参数（例如：无头模式）
options = set_webdriver_options_argument("chrome", [
    "--headless",
    "--disable-gpu",
    "--no-sandbox",
    "--window-size=1920,1080"
])

# 以选项启动
manager = get_webdriver_manager("chrome", options=["--headless", "--disable-gpu"])
```

### DesiredCapabilities

```python
from je_web_runner import get_desired_capabilities, get_desired_capabilities_keys

# 查看可用的功能
keys = get_desired_capabilities_keys()

# 获取浏览器的功能
caps = get_desired_capabilities("CHROME")
```

## 测试记录

所有 WebRunner 动作会自动记录，用于审计追踪及报告生成。

```python
from je_web_runner import test_record_instance

# 启用记录
test_record_instance.set_record_enable(True)

# ... 执行自动化操作 ...

# 访问记录
records = test_record_instance.test_record_list

# 每条记录包含：
# {
#     "function_name": "to_url",
#     "local_param": {"url": "https://example.com"},
#     "time": "2025-01-01 12:00:00",
#     "program_exception": "None"
# }

# 清除记录
test_record_instance.clean_record()
```

## 异常处理

WebRunner 提供完整的自定义异常层次结构：

| 异常 | 说明 |
|------|------|
| `WebRunnerException` | 基础异常 |
| `WebRunnerWebDriverNotFoundException` | 找不到 WebDriver |
| `WebRunnerOptionsWrongTypeException` | 选项类型错误 |
| `WebRunnerArgumentWrongTypeException` | 参数类型错误 |
| `WebRunnerWebDriverIsNoneException` | WebDriver 为 None |
| `WebRunnerExecuteException` | 执行错误 |
| `WebRunnerJsonException` | JSON 处理错误 |
| `WebRunnerGenerateJsonReportException` | JSON 报告生成错误 |
| `WebRunnerAssertException` | 断言失败 |
| `WebRunnerHTMLException` | HTML 报告错误 |
| `WebRunnerAddCommandException` | 命令注册错误 |
| `XMLException` / `XMLTypeException` | XML 处理错误 |
| `CallbackExecutorException` | 回调执行错误 |

## 日志记录

WebRunner 使用轮转式文件处理器记录日志。

- **日志文件：** `WEBRunner.log`
- **日志级别：** WARNING 及以上
- **文件大小上限：** 1 GB
- **格式：** `%(asctime)s | %(name)s | %(levelname)s | %(message)s`

## 支持的浏览器

| 浏览器 | 标识符 |
|--------|--------|
| Google Chrome | `chrome` |
| Chromium | `chromium` |
| Mozilla Firefox | `firefox` |
| Microsoft Edge | `edge` |
| Internet Explorer | `ie` |
| Apple Safari | `safari` |

## 支持的平台

- Windows
- macOS
- Ubuntu / Linux
- Raspberry Pi

## 进阶模块

除核心 WebDriver / 动作执行器外,WebRunner 还提供大量专用模块,每个
模块都在 `je_web_runner/utils/<area>/` 下独立成包,并附完整单元测试。
按能力分类:

### Web 平台 API

- **`webtransport_assert`** — HTTP/3 WebTransport datagram + stream 断言
- **`indexed_db_explorer`** — IndexedDB 快照与对象 / 索引断言
- **`file_system_access`** — 模拟 `showOpenFilePicker` / `showSaveFilePicker` 并记录写入
- **`notifications_audit`** — 追踪 `Notification.requestPermission` 调用时机与策略
- **`sse_assert`** — Server-Sent Events 流录制 + count / data / id 断言
- **`websocket_assert`** — WebSocket frame 录制 + count / payload / pubsub 断言
- **`webrtc_assert`** — PeerConnection 状态 / ICE / track / RTP 断言
- **`view_transitions`** — View Transitions API duration / CLS / group 断言

### 安全 / Headers

- **`mixed_content_audit`** — HTTPS 页面中的 HTTP 资源检测
- **`clickjacking_audit`** — X-Frame-Options + frame-ancestors + iframe 探测
- **`open_redirect_detector`** — 八种 payload 检测 ?redirect= 类漏洞
- **`sri_verify`** — Subresource Integrity hash 存在性 + 正确性验证
- **`coop_coep_audit`** — crossOriginIsolated COOP / COEP + 子资源 CORP/CORS 检查
- **`token_leak_detector`** — 扫描 HAR / log / response 中的 JWT / AWS / GitHub token 等
- **`consent_audit`** — GDPR / CCPA cookie 分类 + 同意前泄漏 / 拒绝后重新植入检测
- **`pii_in_screenshot`** — Screenshot OCR + 隐私 (信用卡 / 身份证 / SSN) 扫描

### 性能预算

- **`inp_tracker`** — Interaction to Next Paint 测量 + p98 + 预算
- **`hydration_check`** — SSR hydration mismatch (DOM diff + console marker)
- **`bundle_budget`** — 每种资源 (script/css/image/font/media) 大小预算
- **`third_party_budget`** — 第三方厂商请求数 / 大小 / 阻塞时间预算
- **`long_animation_frame`** — Long Animation Frame API + 每 script 归因
- **`console_error_budget`** — JS console / unhandled rejection 预算

### 后端集成

- **`grpc_tester`** — gRPC stub 调用录制 + gRPC-Web framing / trailer
- **`webhook_receiver`** — 临时 HTTP server 接收 app 对外 webhook + 断言
- **`idempotency_check`** — 同一请求发送两次,比对 status / body / state / 副作用
- **`pagination_audit`** — 遍历所有页,检测重复 / 漏抓 / cursor loop / 排序错误
- **`backend_log_correlator`** — W3C trace_id → Loki / Elasticsearch / 文件 log 拉取
- **`email_render`** — MailHog / Mailpit / `.eml` 拦截 → 多 viewport 截图

### AI / 工作流

- **`failure_narrator`** — LLM 将 failure bundle 转为自然语言失败摘要
- **`repro_minimizer`** — Delta-debugging (ddmin) 缩减失败 action list
- **`locator_hardener`** — Fragility 评分 + LLM 建议更稳定的 selector
- **`test_categorizer`** — 自动标记 smoke / regression / perf / a11y / security
- **`exploratory_ai`** — Agent 式探索测试员 + 确定性 RandomPlanner
- **`story_to_actions`** — 用户故事 / Figma frame → 验证后的 WR action JSON
- **`session_to_test`** — rrweb / 通用 event stream → WR action JSON
- **`multimodal_qa`** — Screenshot + 问题送 vision LLM 取得 pass/fail 判定
- **`prompt_drift_monitor`** — 追踪 app 内 LLM 功能的输出漂移
- **`test_dedup_ai`** — 结构性 + 语义 embedding 去重 action JSON

### 无障碍 / 国际化 / 视觉

- **`ocr_assert`** — Canvas / WebGL / 图片内 OCR 文本断言
- **`screen_reader_runner`** — 遍历 a11y tree 模拟 NVDA / VoiceOver 朗读顺序
- **`pseudo_localization`** — 字符串伪本地化 + 检测硬编码字符串
- **`forced_colors_mode`** — Dark / reduced-motion / forced-colors / 高对比矩阵

### 治理与报告

- **`pr_risk_score`** — 融合 flake / impact / locator / coverage 信号为 0-100 分
- **`flag_matrix`** — Feature flag 组合矩阵 + 失败最小子集分析
- **`chaos_hooks`** — 种子化 chaos 注入 (离线 / throttle / 中途 reload)
- **`db_snapshot`** — 每个 test 自动 DB savepoint / rollback
- **`time_freezer`** — CDP 注入脚本冻结 `Date` / `performance.now`
- **`persona_runner`** — 同一份 suite × N 种角色矩阵
- **`git_bisect_flake`** — Ledger / probe 两种模式 bisect 出回归 commit
- **`test_cost_estimator`** — 云端分钟 × 费率 → USD + CO₂ 估算
- **`slack_digest`** — Slack Block Kit / Teams Card / 纯文本测试周报
- **`quarantine_age_report`** — Quarantine 条目 + age + 升级 tier
- **`test_debt_dashboard`** — skip / xfail / TODO 盘点 + age + 负责人
- **`sla_tracker`** — 「Y% suite 在 X 分钟内跑完」周 / 日趋势
- **`bug_repro_stability`** — N 次重复 + 分类 deterministic / flaky / 无法重现
- **`test_owners_map`** — CODEOWNERS 解析 + 覆盖层 + 无人认领审计

完整模块树见 [`CLAUDE.md`](../CLAUDE.md);完整命令清单见英文版
[README.md](../README.md) 与 `docs/source/Zh/doc/specialized_modules/`。

## 许可证

本项目采用 [MIT 许可证](../LICENSE)。

Copyright (c) 2021~2023 JE-Chen
