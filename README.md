# WebRunner

<p align="center">
  <strong>A cross-platform web automation framework built on Selenium</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/je-web-runner/"><img src="https://img.shields.io/pypi/v/je_web_runner" alt="PyPI Version"></a>
  <a href="https://pypi.org/project/je-web-runner/"><img src="https://img.shields.io/pypi/pyversions/je_web_runner" alt="Python Version"></a>
  <a href="https://github.com/Intergration-Automation-Testing/WebRunner/blob/main/LICENSE"><img src="https://img.shields.io/github/license/Intergration-Automation-Testing/WebRunner" alt="License"></a>
  <a href="https://webrunner.readthedocs.io/en/latest/"><img src="https://readthedocs.org/projects/webrunner/badge/?version=latest" alt="Documentation Status"></a>
</p>

<p align="center">
  <a href="README/README_zh-TW.md">繁體中文</a> |
  <a href="README/README_zh-CN.md">简体中文</a>
</p>

---

WebRunner (`je_web_runner`) is a cross-platform web automation framework designed to simplify browser automation. It supports multiple browsers, parallel execution, automatic driver management, and generates detailed reports. Built on top of Selenium with additional abstractions, WebRunner helps developers write, run, and manage automation scripts with ease.

## Table of Contents

- [Key Features](#key-features)
- [Installation](#installation)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Core Components](#core-components)
  - [WebDriver Manager](#webdriver-manager)
  - [WebDriver Wrapper](#webdriver-wrapper)
  - [Web Element Wrapper](#web-element-wrapper)
  - [Test Object](#test-object)
- [Action Executor](#action-executor)
  - [Action Format](#action-format)
  - [Available Commands](#available-commands)
  - [Execute from JSON Files](#execute-from-json-files)
- [Report Generation](#report-generation)
- [Remote Automation (Socket Server)](#remote-automation-socket-server)
- [Callback Executor](#callback-executor)
- [Package Manager](#package-manager)
- [Project Template](#project-template)
- [CLI Usage](#cli-usage)
- [WebDriver Options Configuration](#webdriver-options-configuration)
- [Test Record](#test-record)
- [Exception Handling](#exception-handling)
- [Logging](#logging)
- [Supported Browsers](#supported-browsers)
- [Supported Platforms](#supported-platforms)
- [License](#license)

## Key Features

- **Multi-browser support** — Chrome, Chromium, Firefox, Edge, IE, Safari
- **Automatic WebDriver management** — Automatic download and configuration via `webdriver-manager`
- **Parallel execution** — Manage multiple browser instances simultaneously
- **Action executor** — Define automation scripts as JSON action lists
- **Report generation** — HTML, JSON, and XML test reports with success/failure highlighting
- **Remote automation** — TCP socket server for remote command execution
- **Callback system** — Event-driven automation with callback functions
- **Dynamic extension** — Load external Python packages into the executor at runtime
- **Project templates** — Quick-start project structure generation
- **Cross-platform** — Windows, macOS, Ubuntu, Raspberry Pi
- **CLI interface** — Execute automation scripts from the command line
- **Screenshots** — Automatic screenshot capture (PNG, Base64)
- **Comprehensive element interaction** — Locate, click, input, drag-and-drop, and more

## Installation

**Stable version:**

```bash
pip install je_web_runner
```

**Development version:**

```bash
pip install je_web_runner_dev
```

## Requirements

- Python **3.10** or later
- Dependencies: `selenium>=4.0.0`, `requests`, `python-dotenv`, `webdriver-manager`

## Quick Start

### Example 1: Direct API

```python
from je_web_runner import TestObject
from je_web_runner import get_webdriver_manager
from je_web_runner import web_element_wrapper

# Create a WebDriver manager (using Chrome)
manager = get_webdriver_manager("chrome")

# Navigate to a URL
manager.webdriver_wrapper.to_url("https://www.google.com")

# Set implicit wait
manager.webdriver_wrapper.implicitly_wait(2)

# Create a test object to locate the search box by name
search_box = TestObject("q", "name")

# Find the element
manager.webdriver_wrapper.find_element(search_box)

# Click and type into the element
web_element_wrapper.click_element()
web_element_wrapper.input_to_element("WebRunner automation")

# Close the browser
manager.quit()
```

### Example 2: JSON Action List

```python
from je_web_runner import execute_action

actions = [
    ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
    ["WR_to_url", {"url": "https://www.google.com"}],
    ["WR_implicitly_wait", {"time_to_wait": 2}],
    ["WR_SaveTestObject", {"test_object_name": "q", "object_type": "name"}],
    ["WR_find_element", {"element_name": "q"}],
    ["WR_click_element"],
    ["WR_input_to_element", {"input_value": "WebRunner automation"}],
    ["WR_quit"]
]

result = execute_action(actions)
```

## Architecture Overview

```
je_web_runner/
├── __init__.py              # Public API exports
├── __main__.py              # CLI entry point
├── element/
│   └── web_element_wrapper.py   # WebElement interaction wrapper
├── manager/
│   └── webrunner_manager.py     # Multi-driver management
├── webdriver/
│   ├── webdriver_wrapper.py     # Core WebDriver wrapper
│   └── webdriver_with_options.py # Browser options configuration
└── utils/
    ├── callback/                # Callback function executor
    ├── exception/               # Custom exception classes
    ├── executor/                # Action executor engine
    ├── file_process/            # File utilities
    ├── generate_report/         # HTML/JSON/XML report generators
    ├── json/                    # JSON file operations
    ├── logging/                 # Logging configuration
    ├── package_manager/         # Dynamic package loading
    ├── project/                 # Project template generator
    ├── selenium_utils_wrapper/  # Selenium utilities (Keys, Capabilities)
    ├── socket_server/           # TCP socket server for remote control
    ├── test_object/             # Test object & record classes
    ├── test_record/             # Action recording
    └── xml/                     # XML utilities
```

## Core Components

### WebDriver Manager

`WebdriverManager` manages multiple WebDriver instances for parallel browser automation.

```python
from je_web_runner import get_webdriver_manager

# Create a manager with Chrome
manager = get_webdriver_manager("chrome")

# Add another browser instance
manager.new_driver("firefox")

# Switch between browser instances
manager.change_webdriver(0)  # Switch to Chrome
manager.change_webdriver(1)  # Switch to Firefox

# Close a specific driver
manager.close_choose_webdriver(1)  # Close Firefox

# Quit all drivers
manager.quit()
```

### WebDriver Wrapper

`WebDriverWrapper` is the central component that wraps Selenium WebDriver with comprehensive methods.

#### Navigation

```python
wrapper = manager.webdriver_wrapper

wrapper.to_url("https://example.com")
wrapper.forward()
wrapper.back()
wrapper.refresh()
```

#### Element Location

```python
from je_web_runner import TestObject

# Locator strategies: id, name, xpath, css selector, class name, tag name, link text, partial link text
element = TestObject("search-input", "id")
wrapper.find_element(element)      # Find single element
wrapper.find_elements(element)     # Find multiple elements
```

#### Wait Methods

```python
wrapper.implicitly_wait(5)                    # Implicit wait (seconds)
wrapper.explict_wait(10, method=some_func)    # Explicit WebDriverWait
wrapper.set_script_timeout(30)                # Async script timeout
wrapper.set_page_load_timeout(60)             # Page load timeout
```

#### Mouse & Keyboard Actions

```python
wrapper.left_click()
wrapper.right_click()
wrapper.left_double_click()
wrapper.left_click_and_hold()
wrapper.release()
wrapper.drag_and_drop(source_element, target_element)
wrapper.drag_and_drop_offset(element, x=100, y=50)
wrapper.move_to_element(element)              # Hover
wrapper.move_by_offset(100, 200)
wrapper.press_key(keycode)
wrapper.release_key(keycode)
wrapper.send_keys("text")
wrapper.send_keys_to_element(element, "text")
wrapper.perform()                             # Execute queued actions
wrapper.reset_actions()                       # Clear action queue
wrapper.pause(2)                              # Pause in action chain
```

#### Cookie Management

```python
wrapper.get_cookies()                          # Get all cookies
wrapper.get_cookie("session_id")               # Get specific cookie
wrapper.add_cookie({"name": "key", "value": "val"})
wrapper.delete_cookie("session_id")
wrapper.delete_all_cookies()
```

#### JavaScript Execution

```python
wrapper.execute_script("document.title")
wrapper.execute_async_script("arguments[0]('done')", callback)
```

#### Window Management

```python
wrapper.maximize_window()
wrapper.minimize_window()
wrapper.fullscreen_window()
wrapper.set_window_size(1920, 1080)
wrapper.set_window_position(0, 0)
wrapper.get_window_position()
wrapper.get_window_rect()
wrapper.set_window_rect(x=0, y=0, width=1920, height=1080)
```

#### Screenshots & Scrolling

```python
wrapper.get_screenshot_as_png()       # Returns bytes
wrapper.get_screenshot_as_base64()    # Returns base64 string
wrapper.scroll(0, 500)               # Scroll page
```

#### Frame / Window / Alert Switching

```python
wrapper.switch("frame", "frame_name")
wrapper.switch("window", "window_handle")
wrapper.switch("default_content")
```

#### Browser Logs

```python
wrapper.get_log("browser")
```

### Web Element Wrapper

`WebElementWrapper` provides methods for interacting with located elements.

```python
from je_web_runner import web_element_wrapper

web_element_wrapper.click_element()
web_element_wrapper.input_to_element("Hello World")
web_element_wrapper.clear()
web_element_wrapper.submit()

# Inspection
web_element_wrapper.get_attribute("href")
web_element_wrapper.get_property("checked")
web_element_wrapper.get_dom_attribute("data-id")
web_element_wrapper.is_displayed()
web_element_wrapper.is_enabled()
web_element_wrapper.is_selected()
web_element_wrapper.value_of_css_property("color")

# Select (dropdown)
select = web_element_wrapper.get_select()

# Element screenshot
web_element_wrapper.screenshot("element.png")

# Switch active element from a list
web_element_wrapper.change_web_element(2)

# Validate element properties
web_element_wrapper.check_current_web_element({"tag_name": "input"})
```

### Test Object

`TestObject` encapsulates element locator information for reusable element definitions.

```python
from je_web_runner import TestObject, create_test_object, get_test_object_type_list

# Two ways to create
obj1 = TestObject("search", "name")
obj2 = create_test_object("id", "submit-btn")

# View available locator types
print(get_test_object_type_list())
# ['ID', 'NAME', 'XPATH', 'CSS_SELECTOR', 'CLASS_NAME', 'TAG_NAME', 'LINK_TEXT', 'PARTIAL_LINK_TEXT']
```

## Action Executor

The Action Executor is a powerful engine that maps command strings to callable functions. It allows you to define automation scripts as JSON action lists.

### Action Format

Each action is a list with the command name and optional parameters:

```python
["command_name"]                        # No parameters
["command_name", {"key": "value"}]      # Keyword arguments
["command_name", [arg1, arg2]]          # Positional arguments
```

### Available Commands

| Category | Commands |
|----------|----------|
| **Manager** | `WR_get_webdriver_manager`, `WR_change_index_of_webdriver`, `WR_quit` |
| **Navigation** | `WR_to_url`, `WR_forward`, `WR_back`, `WR_refresh` |
| **Elements** | `WR_find_element`, `WR_find_elements`, `WR_find_element_with_test_object_record`, `WR_find_elements_with_test_object_record` |
| **Wait** | `WR_implicitly_wait`, `WR_explict_wait`, `WR_set_script_timeout`, `WR_set_page_load_timeout` |
| **Click** | `WR_left_click`, `WR_right_click`, `WR_left_double_click`, `WR_left_click_and_hold`, `WR_release` |
| **Drag** | `WR_drag_and_drop`, `WR_drag_and_drop_offset`, `WR_drag_and_drop_with_test_object`, `WR_drag_and_drop_offset_with_test_object` |
| **Hover** | `WR_move_to_element`, `WR_move_to_element_with_offset`, `WR_move_by_offset` |
| **Keyboard** | `WR_press_key`, `WR_release_key`, `WR_send_keys`, `WR_send_keys_to_element` |
| **Actions** | `WR_perform`, `WR_reset_actions`, `WR_pause` |
| **Cookies** | `WR_get_cookies`, `WR_get_cookie`, `WR_add_cookie`, `WR_delete_cookie`, `WR_delete_all_cookies` |
| **JavaScript** | `WR_execute_script`, `WR_execute_async_script` |
| **Window** | `WR_maximize_window`, `WR_minimize_window`, `WR_fullscreen_window`, `WR_set_window_size`, `WR_set_window_position`, `WR_set_window_rect` |
| **Screenshot** | `WR_get_screenshot_as_png`, `WR_get_screenshot_as_base64` |
| **Element** | `WR_click_element`, `WR_input_to_element`, `WR_element_clear`, `WR_element_submit`, `WR_element_get_attribute`, `WR_element_is_displayed`, `WR_element_is_enabled`, `WR_element_is_selected` |
| **Test Object** | `WR_SaveTestObject`, `WR_CleanTestObject` |
| **Report** | `WR_generate_html_report`, `WR_generate_json_report`, `WR_generate_xml_report` |
| **Package** | `WR_add_package_to_executor` |
| **Nested** | `WR_execute_action`, `WR_execute_files` |

### Execute from JSON Files

```python
from je_web_runner import execute_files

# Execute actions from JSON files
results = execute_files(["actions1.json", "actions2.json"])
```

JSON file format:

```json
[
    ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
    ["WR_to_url", {"url": "https://example.com"}],
    ["WR_quit"]
]
```

### Add Custom Commands

```python
from je_web_runner import add_command_to_executor

def my_custom_function(param1, param2):
    print(f"Custom: {param1}, {param2}")

add_command_to_executor({"my_command": my_custom_function})
```

## Report Generation

WebRunner can automatically record all actions and generate reports in three formats.

### Enable Recording

```python
from je_web_runner import test_record_instance

test_record_instance.set_record_enable(True)
```

### HTML Report

```python
from je_web_runner import generate_html, generate_html_report

# Generate HTML string
html_content = generate_html()

# Save to file (creates test_results.html)
generate_html_report("test_results")
```

HTML reports include color-coded tables: **aqua** for success, **red** for failure. Each row shows the function name, parameters, timestamp, and exception (if any).

### JSON Report

```python
from je_web_runner import generate_json, generate_json_report

# Generate dicts
success_dict, failure_dict = generate_json()

# Save to files (creates test_results_success.json and test_results_failure.json)
generate_json_report("test_results")
```

### XML Report

```python
from je_web_runner import generate_xml, generate_xml_report

# Generate XML strings
success_xml, failure_xml = generate_xml()

# Save to files (creates test_results_success.xml and test_results_failure.xml)
generate_xml_report("test_results")
```

## Remote Automation (Socket Server)

WebRunner includes a multi-threaded TCP socket server for remote automation control.

### Start Server

```python
from je_web_runner import start_web_runner_socket_server

server = start_web_runner_socket_server(host="localhost", port=9941)
```

### Client Connection

```python
import socket
import json

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("localhost", 9941))

# Send actions as JSON
actions = [
    ["WR_get_webdriver_manager", {"webdriver_name": "chrome"}],
    ["WR_to_url", {"url": "https://example.com"}],
    ["WR_quit"]
]
sock.send(json.dumps(actions).encode("utf-8"))

# Receive results (ends with "Return_Data_Over_JE\n")
response = sock.recv(4096).decode("utf-8")
print(response)

# Shutdown server
sock.send("quit_server".encode("utf-8"))
```

## Callback Executor

Execute automation commands with callback functions triggered on completion.

```python
from je_web_runner import callback_executor

def on_complete():
    print("Navigation complete!")

callback_executor.callback_function(
    trigger_function_name="WR_to_url",
    callback_function=on_complete,
    url="https://example.com"
)
```

With parameters:

```python
def on_element_found(result=None):
    print(f"Element found: {result}")

callback_executor.callback_function(
    trigger_function_name="WR_find_element",
    callback_function=on_element_found,
    callback_function_param={"result": "search_box"},
    callback_param_method="kwargs",
    element_name="search_box"
)
```

## Package Manager

Dynamically load external Python packages into the executor at runtime.

```python
from je_web_runner import execute_action

actions = [
    # Load the 'time' package
    ["WR_add_package_to_executor", {"package": "time"}],
    # Now you can use time.sleep
    ["time_sleep", [2]]
]

execute_action(actions)
```

## Project Template

Generate a quick-start project structure with sample files.

```python
from je_web_runner import create_project_dir

create_project_dir(project_path="./my_project", parent_name="WebRunner")
```

Generated structure:

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

## CLI Usage

WebRunner can be executed directly from the command line.

```bash
# Execute a single JSON action file
python -m je_web_runner -e actions.json

# Execute all JSON files in a directory
python -m je_web_runner -d ./actions/

# Execute a JSON string directly
python -m je_web_runner --execute_str '[["WR_get_webdriver_manager", {"webdriver_name": "chrome"}], ["WR_quit"]]'
```

## WebDriver Options Configuration

Configure browser options before launching.

```python
from je_web_runner import set_webdriver_options_argument, get_webdriver_manager

# Set browser arguments (e.g., headless mode)
options = set_webdriver_options_argument("chrome", [
    "--headless",
    "--disable-gpu",
    "--no-sandbox",
    "--window-size=1920,1080"
])

# Launch with options
manager = get_webdriver_manager("chrome", options=["--headless", "--disable-gpu"])
```

### DesiredCapabilities

```python
from je_web_runner import get_desired_capabilities, get_desired_capabilities_keys

# View available capabilities
keys = get_desired_capabilities_keys()

# Get capabilities for a browser
caps = get_desired_capabilities("CHROME")
```

## Test Record

All WebRunner actions are automatically recorded for audit trails and report generation.

```python
from je_web_runner import test_record_instance

# Enable recording
test_record_instance.set_record_enable(True)

# ... perform automation ...

# Access records
records = test_record_instance.test_record_list

# Each record contains:
# {
#     "function_name": "to_url",
#     "local_param": {"url": "https://example.com"},
#     "time": "2025-01-01 12:00:00",
#     "program_exception": "None"
# }

# Clear records
test_record_instance.clean_record()
```

## Exception Handling

WebRunner provides a hierarchy of custom exceptions:

| Exception | Description |
|-----------|-------------|
| `WebRunnerException` | Base exception |
| `WebRunnerWebDriverNotFoundException` | WebDriver not found |
| `WebRunnerOptionsWrongTypeException` | Invalid options type |
| `WebRunnerArgumentWrongTypeException` | Invalid argument type |
| `WebRunnerWebDriverIsNoneException` | WebDriver is None |
| `WebRunnerExecuteException` | Execution error |
| `WebRunnerJsonException` | JSON processing error |
| `WebRunnerGenerateJsonReportException` | JSON report generation error |
| `WebRunnerAssertException` | Assertion failure |
| `WebRunnerHTMLException` | HTML report error |
| `WebRunnerAddCommandException` | Command registration error |
| `XMLException` / `XMLTypeException` | XML processing error |
| `CallbackExecutorException` | Callback execution error |

## Logging

WebRunner uses a rotating file handler for logging.

- **Log file:** `WEBRunner.log`
- **Log level:** WARNING and above
- **Max file size:** 1 GB
- **Format:** `%(asctime)s | %(name)s | %(levelname)s | %(message)s`

## Supported Browsers

| Browser | Key |
|---------|-----|
| Google Chrome | `chrome` |
| Chromium | `chromium` |
| Mozilla Firefox | `firefox` |
| Microsoft Edge | `edge` |
| Internet Explorer | `ie` |
| Apple Safari | `safari` |

## Supported Platforms

- Windows
- macOS
- Ubuntu / Linux
- Raspberry Pi

## License

This project is licensed under the [MIT License](LICENSE).

