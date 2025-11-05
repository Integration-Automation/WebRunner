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
from je_web_runner import webdriver_wrapper_instance, TestObject

# Create a WebRunner instance
runner = webdriver_wrapper_instance.set_driver(webdriver_name="chrome")

# Open a webpage
runner.get("https://google.com")

# Google search input element
google_input = TestObject("q", "name")

# Find element
google_input_element = webdriver_wrapper_instance.find_element(google_input)

# Print element property
print(google_input_element)

# Click input
webdriver_wrapper_instance.left_click(google_input_element)

# Send keys to element
webdriver_wrapper_instance.send_keys_to_element(google_input_element, "HELLO")

# Take a screenshot
runner.save_screenshot("example.png")

# Close the browser
runner.quit()

```
