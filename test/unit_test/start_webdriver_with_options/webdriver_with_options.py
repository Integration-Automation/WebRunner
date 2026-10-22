"""Exercise manager browser arguments with real Firefox; failures must fail CI."""

from je_web_runner import get_webdriver_manager

webdriver_manager = get_webdriver_manager(
    "firefox", options=["--headless", "--disable-extensions"]
)
try:
    if webdriver_manager.current_webdriver is None:
        raise RuntimeError("Initial Firefox driver was not created")
    webdriver_manager.new_driver("firefox", options=["--headless"])
    if webdriver_manager.current_webdriver is None:
        raise RuntimeError("Second Firefox driver was not created")
    print("webdriver_with_options: both Firefox drivers started successfully")
finally:
    webdriver_manager.quit()
