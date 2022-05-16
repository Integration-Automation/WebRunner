from je_web_runner import get_webdriver_manager

webdriver_manager = get_webdriver_manager("firefox")
webdriver_manager.new_driver("firefox")
webdriver_manager.close_choose_webdriver(1)
webdriver_manager.close_choose_webdriver(0)
webdriver_manager.quit()
