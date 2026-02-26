import os
import sys
import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Path setup
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.utils.config_loader import load_config
from src.scraper import DnpraScraper

def debug_scraping():
    # Load config
    config_path = os.path.join(project_root, "config", "mis_ajustes.yaml")
    config = load_config(config_path)
    
    # Init scraper
    scraper = DnpraScraper(config)
    
    try:
        scraper.init_driver()
        start_url = config["general"]["start_url"]
        selectors = config["selectors"]["certificado_form"]
        
        # Target VIN for debugging (one that resulted in 'Consultado')
        vin = "9BRK4AAG6T0229892" 
        print(f"DEBUG: Processing VIN {vin}")
        
        scraper._navegar_y_cambiar_iframe(start_url)
        
        # Select Nacional
        opt_radio = scraper.wait.until(EC.element_to_be_clickable((By.XPATH, selectors["option_radio"])))
        scraper.driver.execute_script("arguments[0].click();", opt_radio)
        time.sleep(1)
        
        # Input VIN
        vin_input = scraper.wait.until(EC.visibility_of_element_located((By.XPATH, selectors["vin_input"])))
        vin_input.clear()
        vin_input.send_keys(vin)
        
        # Solve Captcha
        print("DEBUG: Solving Captcha...")
        captcha_ok = scraper.solve_captcha_step(selectors["captcha_image"], selectors["captcha_input"])
        
        if not captcha_ok:
            print("DEBUG: Captcha failed.")
            return

        # Submit
        submit_btn = scraper.wait.until(EC.element_to_be_clickable((By.XPATH, selectors["submit_button"])))
        scraper.driver.execute_script("arguments[0].click();", submit_btn)
        
        # Wait for result
        print("DEBUG: Waiting for result...")
        time.sleep(5)
        
        # Capture screenshot of the WHOLE page
        screenshot_path = os.path.join(project_root, "data", "debug_result.png")
        scraper.driver.save_screenshot(screenshot_path)
        print(f"DEBUG: Screenshot saved to {screenshot_path}")
        
        # Check default content
        print("\n--- DEFAULT CONTENT ---")
        try:
            scraper.driver.switch_to.default_content()
        except:
            pass
        body_text = scraper.driver.find_element(By.TAG_NAME, "body").text
        print(f"DEBUG: Default Body snippet: {body_text[:200]}")
        if "Se encontró" in body_text or "dominio" in body_text.lower():
            print("✅ FOUND in Default Content!")
            
        # Check all iframes
        print("\n--- IFRAME CONTENT ---")
        iframes = scraper.driver.find_elements(By.TAG_NAME, "iframe")
        print(f"DEBUG: Found {len(iframes)} iframes.")
        for i, iframe in enumerate(iframes):
            try:
                scraper.driver.switch_to.default_content()
                scraper.driver.switch_to.frame(iframe)
                iframe_text = scraper.driver.find_element(By.TAG_NAME, "body").text
                print(f"DEBUG: Iframe #{i} snippet: {iframe_text[:200]}")
                if "Se encontró" in iframe_text or "dominio" in iframe_text.lower():
                    print(f"✅ FOUND in Iframe #{i}!")
            except Exception as e:
                print(f"DEBUG: Error reading iframe #{i}: {e}")
        
    finally:
        scraper.close()

if __name__ == "__main__":
    debug_scraping()
