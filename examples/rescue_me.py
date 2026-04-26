"""
Demo: open YouTube Music and play OneRepublic — Rescue Me at 100% volume.

Run from the repo root:

    python examples/rescue_me.py

The script launches Chrome with ``--autoplay-policy=no-user-gesture-required``
(YouTube Music blocks ``video.play()`` without a real user gesture otherwise),
navigates to the song's watch URL on music.youtube.com, then forces the
HTMLMediaElement's ``volume`` to 1.0 and calls ``play()`` from JS.
"""
from __future__ import annotations

import sys
import time

from je_web_runner import webdriver_wrapper_instance


RESCUE_ME_URL = "https://music.youtube.com/watch?v=jajHOxvEbXk"
LISTEN_SECONDS = 90


_FORCE_PLAY_JS = """
(() => {
  const video = document.querySelector('video');
  if (!video) { return 'no-video'; }
  video.muted = false;
  video.volume = 1.0;
  const promise = video.play();
  if (promise && typeof promise.catch === 'function') {
    promise.catch(() => {});
  }
  return video.paused ? 'paused' : 'playing';
})()
"""


def _force_play(driver) -> None:
    """Loop the force-play script until the video reports ``playing``."""
    for _ in range(8):
        if driver.execute_script(_FORCE_PLAY_JS) == "playing":
            return
        time.sleep(1)


def main() -> int:
    chrome_args = [
        "--autoplay-policy=no-user-gesture-required",
        "--disable-blink-features=AutomationControlled",
        "--mute-audio=false",
    ]
    try:
        webdriver_wrapper_instance.set_driver("chrome", options=chrome_args)
    except Exception as error:  # pylint: disable=broad-except
        print(f"rescue_me: cannot start chrome ({error!r})", file=sys.stderr)
        return 1

    driver = webdriver_wrapper_instance.current_webdriver
    try:
        webdriver_wrapper_instance.to_url(RESCUE_ME_URL)
        time.sleep(5)
        _force_play(driver)
        time.sleep(LISTEN_SECONDS)
    except Exception as error:  # pylint: disable=broad-except
        print(f"rescue_me: playback failed ({error!r})", file=sys.stderr)
        return 1
    finally:
        try:
            webdriver_wrapper_instance.quit()
        except Exception:  # pylint: disable=broad-except  # nosec B110 — best-effort cleanup; quit failures aren't actionable here
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
