import sys
import time
import tempfile
import shutil
import random
import string
import json
from urllib.parse import urlparse
from flask import Flask, request, jsonify
import logging
from threading import Thread

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def js_click(driver, el):
    driver.execute_script("arguments[0].click();", el)

def find_first(driver_or_el, xpaths):
    for xp in xpaths:
        try:
            els = driver_or_el.find_elements(By.XPATH, xp)
            if els:
                return els[0]
        except:
            continue
    return None

def handle_primefaces_checkbox(driver, wait):
    label_el = find_first(driver, [
        "//label[contains(normalize-space(.), 'Privacy Policy') or contains(normalize-space(.), 'Terms of Service')]",
        "//label[contains(normalize-space(.), 'Privacy') or contains(normalize-space(.), 'Terms')]",
        "//div[contains(@class,'ui-chkbox')]//div[contains(@class,'ui-chkbox-box')]"
    ])
    if label_el:
        js_click(driver, label_el)
        return

    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for fr in frames:
        driver.switch_to.default_content()
        try:
            driver.switch_to.frame(fr)
            checkbox_elements = [
                "//div[contains(@class,'ui-chkbox')]//div[contains(@class,'ui-chkbox-box')]",
                "//label[contains(normalize-space(.), 'Privacy')]",
                "//input[@type='checkbox']"
            ]
            for xpath in checkbox_elements:
                try:
                    el = driver.find_element(By.XPATH, xpath)
                    js_click(driver, el)
                    driver.switch_to.default_content()
                    return
                except:
                    continue
        except:
            continue
        finally:
            driver.switch_to.default_content()

def click_proceed_button(driver, wait):
    proceed_btn = wait.until(EC.element_to_be_clickable((By.ID, "proccedHomeButtonId")))
    js_click(driver, proceed_btn)

def handle_any_dialog_and_proceed(driver, wait, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        dlg = find_first(driver, [
            "//div[contains(@class,'ui-dialog') and contains(@style,'display') and not(contains(@style,'display: none'))]",
            "//div[contains(@class,'modal') and contains(@class,'show')]",
        ])
        if dlg:
            btn = find_first(dlg, [
                ".//button[normalize-space(.)='Proceed']",
                ".//a[normalize-space(.)='Proceed']",
                ".//span[normalize-space(.)='Proceed']/ancestor::button[1]",
                ".//button[contains(@class,'btn') and contains(.,'Proceed')]",
            ])
            if btn:
                js_click(driver, btn)
                return True
        time.sleep(0.1)
    return False

def _mk_temp_profile():
    return tempfile.mkdtemp(prefix="vh_profile_")

def _rand_suffix(n=4):
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(n))

def _get_origin(url):
    u = urlparse(url)
    return f"{u.scheme}://{u.netloc}"

def _hard_clear_state(driver, origin):
    try:
        driver.execute_cdp_cmd("Network.clearBrowserCookies", {})
        driver.execute_cdp_cmd("Network.clearBrowserCache", {})
        driver.delete_all_cookies()
    except Exception:
        pass

def _hard_reload(driver):
    try:
        driver.execute_cdp_cmd("Page.reload", {"ignoreCache": True})
    except Exception:
        driver.refresh()

def handle_prev_session_modal(driver, timeout=3):
    t0 = time.time()
    while time.time() - t0 < timeout:
        dlg = find_first(driver, [
            "//div[contains(@class,'modal') and contains(@class,'show')]",
            "//div[contains(@class,'ui-dialog') and contains(@style,'display')]"
        ])
        if dlg and "Previous session is already active" in dlg.text:
            btn = find_first(dlg, [
                ".//button[contains(@class,'btn-close')]",
                ".//button[normalize-space(.)='OK']",
            ])
            if btn:
                js_click(driver, btn)
                return True
        time.sleep(0.1)
    return False

def backend_logout_sweep(driver, origin):
    candidates = ["/vahanservice/logout", "/vahanservice/vahan/logout"]
    for path in candidates:
        try:
            driver.get(origin + path)
            time.sleep(0.3)
        except Exception:
            pass

def wait_for_page_ready(driver, timeout=15):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    time.sleep(0.5)

def get_mobile_number(reg_no, chassis_no_last5):
    start_time = time.time()
    
    # Input validation
    if not reg_no or not chassis_no_last5:
        return {
            "success": False,
            "mobile_number": "",
            "error": "Registration number and chassis last 5 digits are required",
            "response_time_seconds": round(time.time() - start_time, 2)
        }
    
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    
    # NEW: Anti-detection arguments added
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-images")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # NEW: Anti-detection experimental options
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    _temp_profile = _mk_temp_profile()
    options.add_argument(f"--user-data-dir={_temp_profile}")

    result = {
        "success": False, 
        "mobile_number": "", 
        "error": "",
        "response_time_seconds": 0
    }

    driver = None
    try:
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
        
        # NEW: Execute anti-detection script
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # CHANGED: Increased timeout from 15 to 30
        wait = WebDriverWait(driver, 30)

        homepage_url = "https://vahan.parivahan.gov.in/vahanservice/vahan/ui/statevalidation/homepage.xhtml"
        
        # NEW: Added logging
        logger.info(f"Loading homepage: {homepage_url}")
        driver.get(homepage_url)
        
        # CHANGED: Increased timeout
        wait_for_page_ready(driver, 20)

        origin = _get_origin(driver.current_url)
        backend_logout_sweep(driver, origin)
        _hard_clear_state(driver, origin)
        
        # Fresh load with cache busting
        driver.get(homepage_url + f"?_cb={int(time.time())}{_rand_suffix()}")
        wait_for_page_ready(driver, 20)

        # NEW: Wait for page elements to load
        time.sleep(3)

        try:
            close_btn = driver.find_element(By.CSS_SELECTOR, "#updatemobileno .btn-close")
            js_click(driver, close_btn)
            time.sleep(0.2)
        except:
            pass

        # CHANGED: Improved registration input finding with explicit waits
        regn_input = None
        selectors = [
            (By.ID, "regnid"),
            (By.NAME, "regnid"),
            (By.XPATH, "//input[contains(@id, 'regn')]"),
            (By.XPATH, "//input[contains(@name, 'regn')]"),
            (By.XPATH, "//input[@placeholder]")
        ]
        
        for selector, value in selectors:
            try:
                # NEW: Use explicit wait for each selector
                regn_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((selector, value))
                )
                if regn_input:
                    regn_input.clear()
                    regn_input.send_keys(reg_no)
                    logger.info(f"Entered registration number: {reg_no}")
                    break
            except Exception as e:
                continue

        if not regn_input:
            raise Exception("Could not find registration input field")

        handle_primefaces_checkbox(driver, wait)
        click_proceed_button(driver, wait)

        if handle_prev_session_modal(driver):
            _hard_clear_state(driver, origin)
            _hard_reload(driver)
            time.sleep(2)  # CHANGED: Increased from 0.5 to 2

        handle_any_dialog_and_proceed(driver, wait, timeout=15)  # CHANGED: Increased timeout

        # CHANGED: Increased wait time for URL change
        try:
            WebDriverWait(driver, 30).until(EC.url_contains("login.xhtml"))
            logger.info("Successfully navigated to login page")
        except TimeoutException:
            logger.warning("Timeout waiting for login page, trying recovery...")
            if handle_prev_session_modal(driver):
                _hard_clear_state(driver, origin)
                driver.get(homepage_url + f"?_cb={int(time.time())}{_rand_suffix()}")
                handle_primefaces_checkbox(driver, wait)
                click_proceed_button(driver, wait)
                WebDriverWait(driver, 30).until(EC.url_contains("login.xhtml"))
            else:
                raise Exception("Failed to navigate to login page")

        # CHANGED: Improved fitness icon clicking with explicit waits
        fitness_found = False
        fitness_xpaths = [
            "//a[.//div[contains(text(), 'Re-Schedule Renewal of Fitness Application')]]",
            "//a[contains(@href, 'fitness')]",
            "//a[.//div[contains(text(), 'Fitness')]]",
            "//a[contains(@onclick, 'fitness')]"  # NEW: Added additional selector
        ]
        
        for xpath in fitness_xpaths:
            try:
                fitness_icon = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                js_click(driver, fitness_icon)
                fitness_found = True
                logger.info("Clicked fitness icon")
                break
            except:
                continue

        if not fitness_found:
            raise Exception("Could not find fitness icon")

        # CHANGED: Increased wait time for fitness page
        WebDriverWait(driver, 30).until(EC.url_contains("form_reschedule_fitness.xhtml"))
        
        # CHANGED: Use explicit wait for chassis input
        chassis_input = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "balanceFeesFine:tf_chasis_no"))
        )
        chassis_input.clear()
        chassis_input.send_keys(chassis_no_last5)
        logger.info(f"Entered chassis last 5: {chassis_no_last5}")

        # CHANGED: Use explicit wait for validate button
        validate_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.ID, "balanceFeesFine:validate_dtls"))
        )
        js_click(driver, validate_button)

        # CHANGED: Improved mobile number retrieval with better waiting
        mobile_number = ""
        for i in range(10):  # CHANGED: Increased from 5 to 10 attempts
            try:
                mobile_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "balanceFeesFine:tf_mobile"))
                )
                mobile_number = mobile_input.get_attribute("value")
                if mobile_number and len(mobile_number) >= 10:
                    logger.info(f"Found mobile number: {mobile_number}")
                    break
            except:
                pass
            time.sleep(1)  # CHANGED: Increased from 0.5 to 1 second

        if mobile_number:
            result["success"] = True
            result["mobile_number"] = mobile_number
        else:
            result["error"] = "Mobile number field is empty or not populated"

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Error in get_mobile_number: {error_msg}")
        result["error"] = error_msg

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        try:
            shutil.rmtree(_temp_profile, ignore_errors=True)
        except Exception:
            pass
        
        end_time = time.time()
        result["response_time_seconds"] = round(end_time - start_time, 2)
    
    return result

@app.route('/api/get-mobile', methods=['GET', 'POST'])
def api_get_mobile():
    """API endpoint to get mobile number"""
    start_time = time.time()
    
    if request.method == 'GET':
        reg_no = request.args.get('reg_no', '').upper()
        chassis_last5 = request.args.get('chassis_last5', '')
    else:
        data = request.get_json() if request.is_json else request.form
        reg_no = data.get('reg_no', '').upper()
        chassis_last5 = data.get('chassis_last5', '')
    
    if not reg_no or not chassis_last5:
        return jsonify({
            "success": False,
            "mobile_number": "",
            "error": "Missing parameters: reg_no and chassis_last5 are required",
            "response_time_seconds": round(time.time() - start_time, 2)
        }), 400
    
    try:
        result = get_mobile_number(reg_no, chassis_last5)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "success": False,
            "mobile_number": "",
            "error": f"API error: {str(e)}",
            "response_time_seconds": round(time.time() - start_time, 2)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "vahan-mobile-api",
        "timestamp": time.time()
    })

@app.route('/', methods=['GET'])
def home():
    """Home page with API usage instructions"""
    return jsonify({
        "message": "Vahan Mobile Number API",
        "usage": {
            "GET": "/api/get-mobile?reg_no=REGNO&chassis_last5=CHASSIS5",
            "POST": "/api/get-mobile with JSON: {'reg_no': 'REGNO', 'chassis_last5': 'CHASSIS5'}"
        },
        "example": {
            "reg_no": "DL1ABC1234",
            "chassis_last5": "56789"
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
