# Webrunner
WebRunner is a cross‑platform web automation framework designed to simplify browser automation.
It supports multiple browsers, parallel execution, automatic driver management, 
and generates detailed reports. 
Built on top of Selenium with additional abstractions, WebRunner helps developers write, run, 
and manage automation scripts with ease.

## Key Features

- Multi‑browser support: Chrome, Edge, Safari
- Report generation: JSON / HTML / XML
- Automatic screenshots and window handling
- Element interaction: locate, input, click, and more
- Automatic WebDriver download
- Cross‑platform: Windows, macOS, Ubuntu, Raspberry Pi
- Remote automation and project template


## Installation

```
pip install je_web_runner
```

## Requires

```
python 3.9 or later
```

| All test in test dir

# Quick Start
```python
from je_web_runner import TestObject
from je_web_runner import get_webdriver_manager
from je_web_runner import web_element_wrapper
from je_web_runner import webdriver_wrapper_instance

# 取得 WebDriver 管理器 (這裡使用 Firefox)
# Get webdriver manager (using Firefox here)
driver_wrapper = get_webdriver_manager("firefox")

# 前往 Google 首頁
# Navigate to Google main page
driver_wrapper.webdriver_wrapper.to_url("https://www.google.com")

# 建立測試物件，定位方式為 "name"，名稱為 "q" (Google 搜尋框)
# Create a test object, locate by "name", value "q" (Google search box)
google_input = TestObject("q", "name")

# 設定隱式等待 2 秒
# Set implicit wait to 2 seconds
driver_wrapper.webdriver_wrapper.implicitly_wait(2)

# 尋找目前的網頁元素 (Google 搜尋框)
# Find the current web element (Google search box)
webdriver_wrapper_instance.find_element(google_input)

# 點擊目前的網頁元素
# Click the current web element
web_element_wrapper.click_element()

# 在目前的網頁元素中輸入文字 "abc_test"
# Input text "abc_test" into the current web element
web_element_wrapper.input_to_element("abc_test")

# 關閉瀏覽器
# Close the browser
driver_wrapper.quit()
```
