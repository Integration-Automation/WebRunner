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
        webdriver_wrapper_instance.to_url(COUNTING_STARS_URL)
        # Let the consent dialog (if any) and the player render.
        time.sleep(4)
        # Dismiss EU consent banner if it shows up.
        _click_first_visible(driver, _DISMISS_BUTTON_SELECTORS)
        time.sleep(1)
        # Make sure something is actually playing.
        for _ in range(8):
            state = driver.execute_script(_FORCE_PLAY_JS)
            if state == "playing":
                break
            time.sleep(1)
        # Poll for the skip-ad button for up to 30s; click whatever shows.
        deadline = time.monotonic() + 30
        skipped = False
        while time.monotonic() < deadline:
            ad_state = driver.execute_script(_AD_STATE_JS)
            if ad_state != "ad":
                break
            if _click_first_visible(driver, _SKIP_AD_SELECTORS):
                skipped = True
                time.sleep(1)
                break
            time.sleep(1)
        if not skipped:
            # Wait out non-skippable pre-roll ads up to ~30s more.
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if driver.execute_script(_AD_STATE_JS) != "ad":
                    break
                time.sleep(1)
        # Force-play once more in case the ad transition paused the video.
        driver.execute_script(_FORCE_PLAY_JS)
        time.sleep(LISTEN_SECONDS)
    except Exception as error:  # pylint: disable=broad-except
        print(f"counting_stars: navigation failed ({error!r})", file=sys.stderr)
        return 1
    finally:
        try:
            webdriver_wrapper_instance.quit()
        except Exception:  # pylint: disable=broad-except
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
