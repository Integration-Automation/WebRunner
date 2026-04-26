"""
Demo: open Google, search for "WebRunner Selenium", print the first result title.

Exercises: ``WR_set_driver`` + ``WR_to_url`` + ``WR_save_test_object`` +
``WR_find_recorded_element`` + ``WR_element_input`` + ``WR_press_keys`` +
``WR_sleep``. No Search API — just driving the page like a human.

Run: python examples/google_search.py
"""
from __future__ import annotations

import sys
import time

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from je_web_runner import webdriver_wrapper_instance


SEARCH_TERM = "WebRunner Selenium python automation"


def main() -> int:
    chrome_args = [
        "--disable-blink-features=AutomationControlled",
        "--lang=en-US",
    ]
    try:
        webdriver_wrapper_instance.set_driver("chrome", options=chrome_args)
    except Exception as error:  # pylint: disable=broad-except
        print(f"google_search: cannot start chrome ({error!r})", file=sys.stderr)
        return 1
    driver = webdriver_wrapper_instance.current_webdriver
    try:
        webdriver_wrapper_instance.to_url("https://www.google.com")
        time.sleep(2)
        # Dismiss the EU consent banner if present.
        for selector in (
            "button[aria-label='Reject all']",
            "button[aria-label='Accept all']",
            "div[role='dialog'] button",
        ):
            try:
                btn = driver.find_element(By.CSS_SELECTOR, selector)
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
                    break
            except Exception as miss:  # pylint: disable=broad-except  # nosec B112 — selector probe; log and try next
                print(f"consent selector miss {selector!r}: {miss!r}", file=sys.stderr)
                continue
        # Type into the search box and submit.
        box = driver.find_element(By.CSS_SELECTOR, "textarea[name='q'], input[name='q']")
        box.clear()
        box.send_keys(SEARCH_TERM)
        ActionChains(driver).send_keys(Keys.ENTER).perform()
        time.sleep(2)
        # Read the first result heading.
        first_heading = None
        for selector in ("h3", "[role='heading']"):
            try:
                first_heading = driver.find_element(By.CSS_SELECTOR, selector)
                if first_heading.text.strip():
                    break
            except Exception as miss:  # pylint: disable=broad-except  # nosec B112 — selector probe; log and try next
                print(f"heading selector miss {selector!r}: {miss!r}", file=sys.stderr)
                continue
        if first_heading is not None and first_heading.text.strip():
            print(f"first result: {first_heading.text.strip()[:120]!r}")
        else:
            print("first result: <no heading found>", file=sys.stderr)
            return 1
    finally:
        try:
            webdriver_wrapper_instance.quit()
        except Exception:  # pylint: disable=broad-except  # nosec B110 — best-effort cleanup
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
