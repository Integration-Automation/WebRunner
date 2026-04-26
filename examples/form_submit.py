"""
Demo: fill and submit the httpbin /forms/post sample form.

Combines the new helpers into one realistic flow:

- ``form_autofill`` — infer fields from label/name and emit a fill plan
- ``state_diff``     — capture cookies/storage before & after submission
- ``WR_sleep``       — pace the script

Run: python examples/form_submit.py
"""
from __future__ import annotations

import sys
import time

from selenium.webdriver.common.by import By

from je_web_runner import webdriver_wrapper_instance
from je_web_runner.api.frontend import capture_state, diff_states
from je_web_runner.api.test_data import plan_fill_actions


FORM_URL = "https://httpbin.org/forms/post"

# httpbin's form field metadata (manually projected; the page is static).
FIELDS = [
    {"type": "text",    "name": "custname",  "label": "Customer name"},
    {"type": "tel",     "name": "custtel",   "label": "Telephone"},
    {"type": "email",   "name": "custemail", "label": "Email"},
    {"type": "text",    "name": "comments",  "label": "Comments"},
]

FIXTURE = {
    "custname": "Alice Tester",
    "phone":    "+15551234567",
    "email":    "alice@example.com",
    "comments": "Drove this form via WebRunner cookbook example.",
}


def main() -> int:
    plan = plan_fill_actions(FIELDS, FIXTURE)
    print(f"form_autofill produced {len(plan)} actions")

    chrome_args = ["--disable-blink-features=AutomationControlled"]
    try:
        webdriver_wrapper_instance.set_driver("chrome", options=chrome_args)
    except Exception as error:  # pylint: disable=broad-except
        print(f"form_submit: cannot start chrome ({error!r})", file=sys.stderr)
        return 1

    driver = webdriver_wrapper_instance.current_webdriver
    try:
        webdriver_wrapper_instance.to_url(FORM_URL)
        time.sleep(1)
        before = capture_state(driver)
        # Fill manually using the discovered locators (the executor's
        # WR_save_test_object pipeline would also work, but driving Selenium
        # directly keeps the example readable).
        for field in FIELDS:
            value = FIXTURE.get(field["name"]) or FIXTURE.get(_alias(field["name"])) or ""
            element = driver.find_element(By.NAME, field["name"])
            element.clear()
            element.send_keys(value)
        # Submit and wait for the response page. httpbin's form omits
        # ``type=submit`` so call form.submit() instead of clicking a button.
        driver.find_element(By.TAG_NAME, "form").submit()
        time.sleep(2)
        if "form" not in driver.current_url:
            print(f"submitted -> {driver.current_url}")
        body_text = driver.find_element(By.TAG_NAME, "body").text
        if "Alice Tester" in body_text and "alice@example.com" in body_text:
            print("verified: form values echoed back by httpbin")
        else:
            print("form_submit: response did not echo form values", file=sys.stderr)
            return 1
        after = capture_state(driver)
        diff = diff_states(before, after)
        print(
            f"state diff: cookies(+{len(diff.cookies.added)}/"
            f"-{len(diff.cookies.removed)}) "
            f"local(+{len(diff.local_storage.added)})"
        )
    finally:
        try:
            webdriver_wrapper_instance.quit()
        except Exception:  # pylint: disable=broad-except
            pass
    return 0


def _alias(name: str) -> str:
    return {
        "custname":  "full_name",
        "custtel":   "phone",
        "custemail": "email",
    }.get(name, name)


if __name__ == "__main__":
    sys.exit(main())
