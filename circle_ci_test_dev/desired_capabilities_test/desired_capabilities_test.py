from selenium_wrapper import get_desired_capabilities
from selenium_wrapper import get_desired_capabilities_keys

from selenium_wrapper import get_webdriver

print(get_desired_capabilities_keys())

for keys in get_desired_capabilities_keys():
    print(get_desired_capabilities(keys))

driver_wrapper = get_webdriver("edge", capabilities=get_desired_capabilities("firefox"))
