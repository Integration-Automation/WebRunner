from je_web_runner import webdriver_wrapper

webdriver_wrapper.set_driver("firefox")
webdriver_wrapper.implicitly_wait(5)
webdriver_wrapper.set_page_load_timeout(5)
webdriver_wrapper.set_script_timeout(5)
webdriver_wrapper.quit()
