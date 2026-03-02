"""
Script de diagnóstico: navega al portal DNPRA, clickea Nacional
y reporta el estado del formulario + imagen del captcha.
"""
import time
import base64
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

URL = "https://www.dnrpa.gov.ar/portal_dnrpa/fabr_import2.php?EstadoCertificado=true"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

options = webdriver.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 30)

try:
    print("1. Navegando a la página...")
    driver.get(URL)
    time.sleep(2)

    print("2. Esperando iframe...")
    iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
    driver.switch_to.frame(iframe)
    print("   -> Dentro del iframe.")
    time.sleep(1)

    print("3. Buscando radios...")
    radios = driver.find_elements(By.XPATH, "//input[@type='radio']")
    for r in radios:
        print(f"   Radio: name={r.get_attribute('name')} value={r.get_attribute('value')}")

    print("4. Clickeando Nacional (value=N)...")
    nacional = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='tcert'][@value='N']")))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", nacional)
    time.sleep(0.5)
    nacional.click()
    print("   -> Click hecho.")
    time.sleep(2)

    print("5. Estado del formulario después del click:")
    all_inputs = driver.find_elements(By.XPATH, "//input")
    for inp in all_inputs:
        print(f"   input type={inp.get_attribute('type')} name={inp.get_attribute('name')} visible={inp.is_displayed()}")

    print("6. Buscando imágenes...")
    all_imgs = driver.find_elements(By.XPATH, "//img")
    for img in all_imgs:
        src = img.get_attribute("src") or ""
        alt = img.get_attribute("alt") or ""
        displayed = img.is_displayed()
        print(f"   img alt='{alt}' displayed={displayed} src_prefix='{src[:60]}'")

    print("7. Intentando capturar captcha con diferentes selectores...")
    captcha_selectors = [
        "//img[@alt='Código verificador']",
        "//img[@alt='Codigo verificador']",
        "//img[not(contains(@src,'actualizar'))]",
        "//img[contains(@src,'data:image')]",
        "//img[string-length(@src) > 100]",
    ]
    for sel in captcha_selectors:
        try:
            el = driver.find_element(By.XPATH, sel)
            src = el.get_attribute("src") or ""
            print(f"   ENCONTRADO con '{sel}': src_prefix='{src[:80]}'")
        except Exception:
            print(f"   No encontrado: '{sel}'")

    print("8. Intentando ingresar un VIN de prueba...")
    try:
        vin_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@name='vin']")))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", vin_input)
        vin_input.clear()
        vin_input.send_keys("9BRK4AAG6T0229892")
        print("   -> VIN ingresado.")
        time.sleep(2)
    except Exception as e:
        print(f"   Error con VIN: {e}")

    print("9. Buscando imágenes DE NUEVO (después del VIN)...")
    all_imgs = driver.find_elements(By.XPATH, "//img")
    for img in all_imgs:
        src = img.get_attribute("src") or ""
        alt = img.get_attribute("alt") or ""
        displayed = img.is_displayed()
        src_len = len(src)
        print(f"   img alt='{alt}' displayed={displayed} src_len={src_len} src_prefix='{src[:80]}'")

    print("10. Guardando captcha si lo encuentra...")
    for sel in captcha_selectors:
        try:
            img_el = driver.find_element(By.XPATH, sel)
            if not img_el.is_displayed():
                continue
            img_src = driver.execute_script("return arguments[0].src;", img_el)
            if img_src and img_src.startswith("data:image"):
                _, b64 = img_src.split(",", 1)
                path = os.path.join(OUTPUT_DIR, "diag_captcha.png")
                with open(path, "wb") as f:
                    f.write(base64.b64decode(b64))
                print(f"    -> ✅ Captcha guardado en: {path} (selector: {sel})")
                break
        except Exception as e:
            print(f"    Error con {sel}: {e}")

    print("\n--- DIAGNÓSTICO COMPLETO ---")
    print("Dejando la ventana abierta 15 segundos para revisión visual...")
    time.sleep(15)

except Exception as ex:
    print(f"ERROR GENERAL: {ex}")
finally:
    driver.quit()
    print("Driver cerrado.")
