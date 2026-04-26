"""
Demo: open YouTube and play OneRepublic — Counting Stars.

Run from the repo root:

    python examples/counting_stars.py

The script launches Chrome with the ``--autoplay-policy=no-user-gesture-required``
flag (Chrome blocks autoplay-with-sound by default), navigates to the
regular YouTube watch URL, forces ``video.play()`` from JS to bypass any
remaining autoplay gate, then polls for the *Skip Ad* button so a pre-roll
ad doesn't eat the listen window.
"""
from __future__ import annotations

import sys
import time

from je_web_runner import webdriver_wrapper_instance


COUNTING_STARS_URL = "https://www.youtube.com/watch?v=hT_nvWreIhg"
LISTEN_SECONDS = 90
# YouTube cycles through these skip-button selectors every couple of years.
_SKIP_AD_SELECTORS = [
    ".ytp-skip-ad-button",
    ".ytp-ad-skip-button",
    ".ytp-ad-skip-button-modern",
    "button[aria-label*='Skip Ad' i]",
    "button[aria-label*='Skip Ads' i]",
]
_DISMISS_BUTTON_SELECTORS = [
    "button[aria-label='Reject all']",
    "button[aria-label='Accept all']",
    "tp-yt-paper-button[aria-label*='Reject']",
    "tp-yt-paper-button[aria-label*='Accept']",
]


_FORCE_PLAY_JS = """
(() => {
  const video = document.querySelector('video');
  if (!video) { return 'no-video'; }
  video.muted = false;
  const promise = video.play();
  if (promise && typeof promise.catch === 'function') {
    promise.catch(() => {});
  }
  return video.paused ? 'paused' : 'playing';
})()
"""


_AD_STATE_JS = """
(() => {
  // Ad-showing class lives on the player root.
  const player = document.querySelector('.html5-video-player');
  if (!player) { return 'no-player'; }
  return player.classList.contains('ad-showing') ? 'ad' : 'video';
})()
"""


def _click_first_visible(driver, selectors) -> bool:
    """Click the first selector whose element is visible; return whether one fired."""
    script = """
    const selectors = arguments[0];
    for (const css of selectors) {
      const el = document.querySelector(css);
      if (el && el.offsetParent !== null) {
        el.click();
        return css;
      }
    }
    return null;
    """
    return bool(driver.execute_script(script, selectors))


def _force_play(driver) -> None:
    """Loop the force-play script until the video reports ``playing``."""
    for _ in range(8):
        if driver.execute_script(_FORCE_PLAY_JS) == "playing":
            return
        time.sleep(1)


def _await_ad_clear(driver, max_seconds: float = 30.0) -> bool:
    """Poll ``_AD_STATE_JS``; click skip-ad if visible. Returns True on skip."""
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        if driver.execute_script(_AD_STATE_JS) != "ad":
            return False
        if _click_first_visible(driver, _SKIP_AD_SELECTORS):
            time.sleep(1)
            return True
        time.sleep(1)
    return False


def _wait_out_unskippable_ad(driver, max_seconds: float = 30.0) -> None:
    """Tick until ``_AD_STATE_JS`` reports ``video`` or budget runs out."""
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        if driver.execute_script(_AD_STATE_JS) != "ad":
            return
        time.sleep(1)


def _navigate_and_play(driver) -> None:
    webdriver_wrapper_instance.to_url(COUNTING_STARS_URL)
    time.sleep(4)
    _click_first_visible(driver, _DISMISS_BUTTON_SELECTORS)
    time.sleep(1)
    _force_play(driver)
    if not _await_ad_clear(driver):
        _wait_out_unskippable_ad(driver)
    # Force-play once more in case the ad transition paused the video.
    driver.execute_script(_FORCE_PLAY_JS)


def main() -> int:
    chrome_args = [
        "--autoplay-policy=no-user-gesture-required",
        "--disable-blink-features=AutomationControlled",
        "--mute-audio=false",
    ]
    try:
        webdriver_wrapper_instance.set_driver("chrome", options=chrome_args)
    except Exception as error:  # pylint: disable=broad-except
        print(f"counting_stars: cannot start chrome ({error!r})", file=sys.stderr)
        return 1

    driver = webdriver_wrapper_instance.current_webdriver
    try:
        _navigate_and_play(driver)
        time.sleep(LISTEN_SECONDS)
    except Exception as error:  # pylint: disable=broad-except
        print(f"counting_stars: navigation failed ({error!r})", file=sys.stderr)
        return 1
    finally:
        try:
            webdriver_wrapper_instance.quit()
        except Exception:  # pylint: disable=broad-except  # nosec B110 — best-effort cleanup; quit failures aren't actionable here
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
