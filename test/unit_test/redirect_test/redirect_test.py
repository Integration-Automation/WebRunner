import sys

from je_web_runner import webdriver_wrapper_instance

try:
    webdriver_wrapper_instance.set_driver("firefox")
    webdriver_wrapper_instance.implicitly_wait(5)
    webdriver_wrapper_instance.to_url("https://music.youtube.com/")
    webdriver_wrapper_instance.back()
    webdriver_wrapper_instance.refresh()
    webdriver_wrapper_instance.forward()
    webdriver_wrapper_instance.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(1)
