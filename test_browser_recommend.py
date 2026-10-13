"""
test_browser_recommend.py
Tests frontend connected to reloaded backend via Playwright.
"""

import time
from playwright.sync_api import sync_playwright

def test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        print("Navigating to http://localhost:3000/recommend ...")
        page.goto("http://localhost:3000/recommend", wait_until="networkidle", timeout=30000)
        time.sleep(1)

        # 1. Test Ambiguous Query 'pvc'
        print("Entering query: 'pvc'")
        textarea = page.locator("textarea")
        textarea.fill("pvc")
        page.keyboard.press("Enter")

        # Wait for modal to appear
        print("Waiting for Disambiguation modal...")
        page.wait_for_selector("text=Specification Refinement Needed", timeout=15000)
        time.sleep(1)
        page.screenshot(path="C:/Users/devag/.gemini/antigravity/brain/180812d1-acd1-431d-bc0a-d03591fc2d2c/screenshot_reloaded_modal.png")
        print("Captured screenshot_reloaded_modal.png")

        # 2. Select first option
        print("Selecting option 1...")
        first_option = page.locator("button:has-text('IS 14735:1999')").first
        first_option.click()

        # Wait for recommendation card to appear
        print("Waiting for Recommended Standard card...")
        page.wait_for_selector("text=Recommended Standard", timeout=20000)
        time.sleep(1)
        page.screenshot(path="C:/Users/devag/.gemini/antigravity/brain/180812d1-acd1-431d-bc0a-d03591fc2d2c/screenshot_reloaded_result.png")
        print("Captured screenshot_reloaded_result.png")

        browser.close()
        print("All tests completed successfully!")

if __name__ == "__main__":
    test()
