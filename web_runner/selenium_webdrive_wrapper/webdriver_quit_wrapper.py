
def quit_wrapper(webdriver, current_webdriver_list):
    for not_closed_webdriver in current_webdriver_list:
        not_closed_webdriver.close()
    webdriver.quit()
