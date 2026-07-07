from seleniumbase import Driver
import json
import time
import random
import os
from datetime import datetime, timezone
# ===== Settings =====
SCROLL_SPEED = 10   # pixels per step (lower = slower & smoother)
RUN_TIME = 100      # total scroll duration
LOOPS = 5   
Gif="gif"        # number of processing cycles per account

def human_sleep(mode="short"):
    ranges = {
        "tiny":  (0.15, 0.6),   # micro pause before/after click
        "short": (0.8,  2.5),   # normal browsing
        "mid":   (2.5,  6.5),   # reading a tweet
        "long":  (8.0,  20.0),  # “distraction” / thinking
    }
    a, b = ranges.get(mode, ranges["short"])
    time.sleep(random.uniform(a, b))

# ===== Setup Browser =====
def setup(cookie_name):
    """Create browser and load cookies correctly with Edge spoofing"""

    # 1. Add Edge User-Agent to match your cookie source
    # This prevents X from flagging the session as a mismatch
    edge_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
    
    # Initialize driver with UC mode and Edge User-Agent
    driver = Driver(uc=True, agent=edge_ua)

    # Open a neutral page on the target domain first
    try: 
        driver.uc_open_with_reconnect("https://x.com/robots.txt", reconnect_time=5)
        driver.uc_gui_click_captcha()
    except Exception as e:
        print(f"Not Found: Captacha")
    time.sleep(2) 

    driver.delete_all_cookies()

    cookies_file = os.path.join("private_data", f"{cookie_name}.json")

    try:
        with open(cookies_file, "r") as f:
            cookies = json.load(f)
    except FileNotFoundError:
        print(f"Error: Cookie file not found at {cookies_file}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in cookie file at {cookies_file}")
        return None

    # Remove legacy cookie that conflicts with modern auth and causes login failure
    before = len(cookies)
    cookies = [c for c in cookies if c["name"] != "_twitter_sess"]
    if len(cookies) < before:
        print("Removed _twitter_sess (legacy cookie that breaks login)")

    for cookie in cookies:
        try:
            # Build the base cookie dictionary
            clean_cookie = {
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie.get("domain", ".x.com"),
                "path": cookie.get("path", "/"),
                "secure": cookie.get("secure", True) # Explicitly set security flag
            }

            # Fix: Map 'no_restriction' (from your JSON) to 'None' (Selenium standard)
            same_site = cookie.get("sameSite")
            if isinstance(same_site, str):
                ss_lower = same_site.lower()
                if ss_lower == "no_restriction":
                    clean_cookie["sameSite"] = "None"
                elif ss_lower in ["strict", "lax"]:
                    clean_cookie["sameSite"] = same_site.capitalize()

            # Fix: Ensure expiry is a strictly formatted integer
            if "expirationDate" in cookie:
                try:
                    clean_cookie["expiry"] = int(float(cookie["expirationDate"]))
                except (ValueError, TypeError):
                    pass

            driver.add_cookie(clean_cookie)

        except Exception as e:
            # Silently fail on non-critical cookies like 'g_state'
            pass

    # Refresh or navigate to home to apply cookies
    try:
        driver.uc_open_with_reconnect("https://x.com/home", reconnect_time=5)
        driver.uc_gui_click_captcha()
    except Exception as e:
        print(f" Not found: Captacha") 
    time.sleep(5) # Give the dashboard time to load
    driver.save_screenshot("error_screenshot.png")
    # Simple login validation
    current_url = driver.current_url.lower()

    if "/login" in current_url or "flow" in current_url:
        print(f"❌ Cookie login failed. Current URL: {current_url}")
        # Save screenshot for GitHub Action artifacts
        return None

    print("✅ Cookie login successful")
    return driver
# ===== Smooth Scrolling =====

def smooth_scroll(driver):
    scroll_times = random.randint(2, 7)
    for _ in range(scroll_times):
        scroll(driver)
        time.sleep(random.uniform(1.2, 4.5))
    screenshot_path = os.path.join(os.environ.get("GITHUB_WORKSPACE", "."), "debug.png")
    driver.save_screenshot(screenshot_path)
    print(f"📸 Screenshot saved to: {screenshot_path}")
def scroll(driver, duration=RUN_TIME, step=SCROLL_SPEED):
    print("🌀 Scrolling...")

    # randomize total scroll duration per call
    duration = random.uniform(duration * 0.6, duration * 1.4)

    start = time.time()
    y = 0

    while time.time() - start < duration:

        # vary step (speed variation)
        current_step = step * random.uniform(0.7, 1.3)
        y += current_step

        driver.execute_script(f"window.scrollTo(0, {y});")

        # micro delay between scroll steps
        time.sleep(random.uniform(0.05, 0.12))

        # ⭐ reading pause (most important)
        if random.random() < 0.12:
            human_sleep("mid")

        # ⭐ occasional early stop (very human)
        if random.random() < 0.03:
            break
    print("🎯 Done scrolling.")

def GotoProfile(driver,url):
    try:
        driver.get(url)
        print("✅ Navigated to profile")
        human_sleep("mid")
        smooth_scroll(driver)
        human_sleep("tiny")
        driver.execute_script("window.scrollTo(0, 0);")
        human_sleep("short")
        return True
    except Exception as e:
        print("❌ Profile navigation failed:", e)
        return False
# ===== Retweet Post =====
def retweet_to_community(driver):
    try:
        # open retweet menu
        if not driver.is_element_present('[data-testid="retweet"]'):
            print("⚠️ No retweet button")
            return False

        human_sleep("tiny")
        driver.click('[data-testid="retweet"]')
        human_sleep("tiny")

        # click Quote (fixed selector)
        try:
            driver.wait_for_element("//a[@role='menuitem']//span[contains(text(),'Quote')]", timeout=5)
            driver.click("//a[@role='menuitem']//span[contains(text(),'Quote')]")
        except Exception:
            print("⚠️ Quote option missing")
            driver.press_keys("body", "ESC")
            return False

        human_sleep("mid")

       # audience selector
        try:
            driver.wait_for_element_visible('div[role="dialog"]', timeout=10)
            
            # Selector for the audience toggle
            audience_btn = 'button[aria-label="Choose audience"]'
            
            # Check if dropdown is ALREADY open (looking for "My Communities" text)
            if not driver.is_text_visible("My Communities"):
                print("Opening audience dropdown...")
                # Use js_click to bypass the "click intercepted" error
                driver.js_click(audience_btn) 
            else:
                print("Audience dropdown already open, proceeding...")
            human_sleep("short")
        except Exception as e:
            print(f"⚠️ Audience selector failed: {e}")
            driver.save_screenshot("audience_error.png")
            driver.press_keys("body", "ESC")
            return False
        # try:
        #     driver.wait_for_element('div[role="dialog"]', timeout=10)
        #     human_sleep("short")

        #     # Locate the real button
        #     audience_btn = 'button[aria-label="Choose audience"]'

        #     driver.wait_for_element(audience_btn, timeout=8)

        #     expanded = driver.get_attribute(audience_btn, "aria-expanded")

        #     # If closed → open it
        #     if expanded == "false":
        #         driver.click(audience_btn)
        #         human_sleep("short")

        #     # If already open → do nothing
        #     elif expanded == "true":
        #         print("Audience dropdown already open")

        #     # Confirm dropdown content exists
        #     driver.wait_for_element("//span[text()='My Communities']", timeout=8)

        # except Exception as e:
        #     print("⚠️ Audience selector failed:", e)
        #     driver.save_screenshot("audience_debug.png")
        #     driver.press_keys("body", "ESC")
        #     return False

        # select community
        
        try:
            with open("community.txt", "r", encoding="utf-8") as f:
                for name in f:
                    community_name= name.strip()
                    try:
                        driver.wait_for_element(
                            f"//div[@role='menuitem']//span[contains(text(),'{community_name}')]",
                            timeout=8
                        )

                        driver.click(
                            f"//div[@role='menuitem'][.//span[contains(text(),'{community_name}')]]"
                        )
                        print(f"✔ Selected community: {community_name}")
                        break
                    except Exception:
                        continue
            human_sleep("short")
        except Exception as e:
            print("⚠️ Community not found:", e)
            driver.save_screenshot("community_debug.png")
            driver.press_keys("body", "ESC")
            return False

        # optional comment (random)
        try:
            print("STEP 1: Waiting for textarea...")
            driver.wait_for_element_visible(
                '[data-testid^="tweetTextarea"]',
                timeout=10
            )
            print("✔ STEP 1 PASSED")
            dismiss_modal_if_present(driver)
            print("STEP 2: Clicking textarea...")
            driver.click('[data-testid^="tweetTextarea"]')
            print("✔ STEP 2 PASSED")

            human_sleep("tiny")

            print("STEP 3: Typing text...")
            driver.type(
                 '[contenteditable="true"][role="textbox"]', TextRetweet()      
            )
            print("✔ STEP 3 PASSED")

            human_sleep("short")

            print("STEP 4: Checking typed value...")
            typed_text = driver.get_text('[data-testid^="tweetTextarea"]')
            print("TEXT FOUND:", repr(typed_text))

        except Exception as e:
            print("❌ ERROR OCCURRED:", e)

                # post
        try:
            driver.wait_for_element('[data-testid="tweetButton"]', timeout=5)
            human_sleep("tiny")

            try:
                driver.click('[data-testid="tweetButton"]')
            except:
                driver.js_click('[data-testid="tweetButton"]')

            print("✅ Shared to community")
            human_sleep("short")
            return True

        except Exception:
            print("⚠️ Post failed")
            driver.press_keys("body", "ESC")
            return False

    except Exception as e:
        print("❌ Community retweet error:", e)
        driver.press_keys("body", "ESC")
        return False
def TextRetweet():
    with open("TextRetweet.txt", "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        return None
    return random.choice(lines)
def CommunityRetweet(account):
    try:
        with open("community_list.json", "r", encoding="utf-8") as f:
            data = json.load(f)   # load full JSON list
    except Exception as e:
        print("Error loading JSON:", e)
        return None

    # Find the matching account
    for item in data:
        if item.get("account") == account:
            communities = item.get("community", [])
            if communities:
                return random.choice(communities)
            return None
    return None
def dismiss_modal_if_present(driver):
    try:
        if driver.is_element_visible("span:contains('Got it')"):
            driver.click("span:contains('Got it')")
            driver.sleep(1)  # wait for modal to fully close
            print("Modal dismissed!")
    except Exception:
        pass
def work(driver,*args):
    if not args:
        url="https://x.com/AngeTjand936"
    else:
        for item in args:
            url=item
    if driver is None:
        print("❌ Driver is None — skipping work(). Cookie login likely failed.")
        return
    if random.random() < 0.9:
        print("active session")
        smooth_scroll(driver)
        if random.random() < 0.9:
            GotoProfile(driver,url)
            time.sleep(random.uniform(2, 5))
            retweet_to_community(driver)
    else:
        # Passive session
        print("passive session")
        scroll_times = random.randint(3,5)
        for _ in range(scroll_times):
            smooth_scroll(driver)
            time.sleep(random.uniform(1.5, 5))
    driver.save_screenshot("debug.png")
    driver.quit()