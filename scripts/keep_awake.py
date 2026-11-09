"""Open the Streamlit Cloud app in a real headless browser so it counts as a visit.

Plain HTTP pings don't keep a Community Cloud app awake: the URL redirects through an
auth page and only a browser session reaches the app. This script:
  1. opens the app in headless Chromium,
  2. clicks "Yes, get this app back up!" if the app is asleep,
  3. waits until VisionFit's own sign-in screen renders, and exits non-zero otherwise.

Usage:  python scripts/keep_awake.py [APP_URL]
"""
import sys
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

APP_URL = sys.argv[1] if len(sys.argv) > 1 else "https://kfqb7msiivnxubjezjte7p.streamlit.app/"
WAKE_BUTTON = "Yes, get this app back up!"
APP_MARKER = "Start training"     # text on VisionFit's sign-in screen
MAX_WAIT_SECONDS = 240


def find_in_frames(page, text):
    """The app renders inside an iframe on Streamlit Cloud, so search every frame."""
    for frame in page.frames:
        try:
            if frame.get_by_text(text, exact=False).count() > 0:
                return frame
        except Exception:
            continue
    return None


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        print(f"Opening {APP_URL}")
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=90_000)

        deadline = time.time() + MAX_WAIT_SECONDS
        woke = False

        while time.time() < deadline:
            if find_in_frames(page, APP_MARKER):
                print("App is awake: sign-in screen rendered.")
                browser.close()
                return 0

            frame = find_in_frames(page, WAKE_BUTTON)
            if frame and not woke:
                print("App was asleep, clicking the wake-up button.")
                try:
                    frame.get_by_text(WAKE_BUTTON, exact=False).first.click(timeout=10_000)
                    woke = True
                except PlaywrightTimeout:
                    print("Wake-up button was not clickable yet, retrying.")

            time.sleep(5)

        page.screenshot(path="keep-awake-failure.png", full_page=True)
        print(f"App did not load within {MAX_WAIT_SECONDS}s. Page title: {page.title()!r}")
        browser.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())
