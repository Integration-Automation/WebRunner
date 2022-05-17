from je_web_runner import webdriver_wrapper

webdriver_wrapper.set_driver("firefox")
webdriver_wrapper.implicitly_wait(5)
webdriver_wrapper.to_url("https://music.youtube.com/")
webdriver_wrapper.back()
webdriver_wrapper.refresh()
webdriver_wrapper.forward()
webdriver_wrapper.quit()
