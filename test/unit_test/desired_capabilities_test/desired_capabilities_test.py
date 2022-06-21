import sys

from je_web_runner import get_desired_capabilities
from je_web_runner import get_desired_capabilities_keys
from je_web_runner import get_webdriver_manager

try:
    print(get_desired_capabilities_keys())

    for keys in get_desired_capabilities_keys():
        print(get_desired_capabilities(keys))

    driver_wrapper = get_webdriver_manager("firefox", capabilities=get_desired_capabilities("firefox"))
    driver_wrapper.quit()
except Exception as error:
    print(repr(error), file=sys.stderr)
    sys.exit(0)
