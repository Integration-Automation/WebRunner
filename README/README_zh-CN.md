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

## 许可证

本项目采用 [MIT 许可证](../LICENSE)。

Copyright (c) 2021~2023 JE-Chen
