from selenium_wrapper import get_desired_capabilities
from selenium_wrapper import get_desired_capabilities_keys


print(get_desired_capabilities_keys())

for keys in get_desired_capabilities_keys():
    print(get_desired_capabilities(keys))
