========
Backends
========

Selenium (default)
==================

The original ``WebDriverWrapper`` plus ``WebElementWrapper``. All commands
without a more specific prefix dispatch here.

Playwright
==========

A full mirror of the Selenium surface lives under ``WR_pw_*``:

* Lifecycle / pages / navigation
* Find (with ``TestObject`` translation) and direct page-level shortcuts
* Element-level wrapper
* Mobile emulation, locale, timezone, geolocation, permissions, clock
* HAR recording, route mocking, console + network event capture
* Network throttling presets via CDP

Switch is opt-in: existing scripts keep running on Selenium.

Cloud Grid
==========

Provider helpers for BrowserStack, Sauce Labs, and LambdaTest:

* ``connect_browserstack`` / ``connect_saucelabs`` / ``connect_lambdatest``
* ``build_browserstack_capabilities`` / ``build_saucelabs_capabilities`` /
  ``build_lambdatest_capabilities``
* ``start_remote_driver`` for arbitrary hub URLs

Appium (mobile)
===============

``start_appium_session`` builds an Appium WebDriver and registers it on the
shared Selenium wrapper so existing ``WR_*`` commands keep working against a
mobile session. Capability builders cover both Android (UiAutomator2) and
iOS (XCUITest).

``appium_integration.gestures`` adds higher-level mobile gestures —
``swipe`` / ``scroll`` / ``long_press`` / ``pinch`` / ``double_tap``
prefer Appium's ``mobile:`` named extensions and fall back to W3C Actions
sequences.
