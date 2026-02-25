import logging
import os
import time
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    WebDriverException, NoSuchWindowException,
    InvalidSessionIdException, TimeoutException
)

from src.utils.captcha_breaker import CaptchaBreaker
from src.utils.data_handler import DataHandler


class DnpraScraper:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.driver = None
        self.wait = None

        # Inicializar el rompedor de captchas
        tesseract_cmd = os.getenv('TESSERACT_CMD_PATH', r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        self.captcha_breaker = CaptchaBreaker(tesseract_cmd_path=tesseract_cmd)

        # Handler de Excel
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        excel_rel_path = self.config["general"]["input_excel_path"]
        excel_abs_path = os.path.join(self.project_root, excel_rel_path)
        self.data_handler = DataHandler(excel_abs_path)

    def _kill_stray_processes(self):
        """Mata procesos de Chrome y ChromeDriver que hayan quedado colgados."""
        for proc in ["chromedriver.exe", "chrome.exe"]:
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", proc],
                    capture_output=True, timeout=5
                )
            except Exception:
                pass
        time.sleep(2)

    def init_driver(self):
        """Inicializa Selenium de manera robusta, limpiando procesos previos."""
        self.logger.info("Inicializando el navegador...")
        self._kill_stray_processes()

        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # options.add_argument("--headless")  # Descomentar para producción

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.maximize_window()
        timeout = self.config.get("general", {}).get("timeout_seconds", 30)
        self.wait = WebDriverWait(self.driver, timeout=timeout)
        self.logger.info("✅ Navegador listo.")

    def _reset_driver(self):
        """Quita el driver viejo y lo re-inicializa limpiamente."""
        self.logger.warning("Reseteando navegador...")
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None
        self.wait = None
        time.sleep(3)
        self.init_driver()

    def _is_driver_alive(self):
        """Verifica si el driver sigue activo."""
        try:
            _ = self.driver.current_url
            return True
        except Exception:
            return False

    def _navegar_y_cambiar_iframe(self, start_url):
        """Navega a la URL y hace switch al iframe del formulario."""
        self.driver.get(start_url)
        time.sleep(2)

        # El formulario está DENTRO de un iframe. Hay que cambiar el contexto.
        iframe = self.wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "iframe"))
        )
        self.driver.switch_to.frame(iframe)
        self.logger.info("  -> Dentro del iframe del formulario.")
        time.sleep(1)

    def start_scraping(self):
        """Método principal que coordina el scraping masivo desde Excel."""
        results = {}
        dominios = {}
        try:
            self.init_driver()

            # Cargar VINs pendientes (FIFO)
            self.logger.info("Buscando VINs pendientes en Excel...")
            vins = self.data_handler.get_pending_vins()

            if not vins:
                self.logger.info("No hay VINs pendientes por procesar.")
                return

            self.logger.info(f"Se encontraron {len(vins)} VINs pendientes.")

            # Cargar el mapa Nacional/Importado desde Nro.Fabr.
            tipo_map = self.data_handler.get_tipo_map()

            start_url = self.config["general"]["start_url"]
            selectors = self.config["selectors"]["certificado_form"]
            consecutive_errors = 0

            for i, vin in enumerate(vins):
                self.logger.info(f"[{i+1}/{len(vins)}] Procesando VIN: {vin}")

                try:
                    # Verificar sesión y re-inicializar si es necesario
                    if not self._is_driver_alive():
                        self._reset_driver()

                    # Navegar y entrar al iframe
                    self._navegar_y_cambiar_iframe(start_url)

                    # --- PASO 1: Seleccionar Nacional o Importado según Nro.Fabr. ---
                    tipo = tipo_map.get(str(vin), 'N')  # 'N'=Nacional, 'I'=Importado
                    radio_xpath = f"//input[@name='tcert'][@value='{tipo}']"
                    tipo_label = 'Nacional' if tipo == 'N' else 'Importado'
                    self.logger.info(f"  -> Seleccionando tipo '{tipo_label}' ({tipo}) para VIN {vin}")
                    opt_radio = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, radio_xpath))
                    )
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", opt_radio
                    )
                    time.sleep(0.5)
                    try:
                        opt_radio.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", opt_radio)
                    time.sleep(1)

                    # --- PASO 2: Ingresar VIN ---
                    self.logger.info(f"  -> Ingresando VIN: {vin}")
                    vin_input = self.wait.until(
                        EC.visibility_of_element_located((By.XPATH, selectors["vin_input"]))
                    )
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", vin_input
                    )
                    time.sleep(0.3)
                    vin_input.clear()
                    vin_input.send_keys(str(vin))

                    # --- PASO 3: Resolver Captcha ---
                    # Esperamos un poco para que el captcha se cargue
                    time.sleep(2)
                    self.logger.info("  -> Resolviendo Captcha...")
                    captcha_ok = self.solve_captcha_step(
                        selectors["captcha_image"], selectors["captcha_input"]
                    )

                    if not captcha_ok:
                        self.logger.error(f"  !! No se pudo resolver el captcha para VIN {vin}.")
                        results[vin] = "ERROR_CAPTCHA"
                        consecutive_errors += 1
                        continue

                    # --- PASO 4: Enviar Formulario ---
                    self.logger.info("  -> Enviando consulta...")
                    submit_btn = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selectors["submit_button"]))
                    )
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", submit_btn
                    )
                    time.sleep(0.3)
                    try:
                        submit_btn.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", submit_btn)

                    # --- PASO 5: Leer Resultado ---
                    time.sleep(3)
                    try:
                        # Salir del iframe para leer el resultado (el portal lo renderiza en el main doc)
                        try:
                            self.driver.switch_to.default_content()
                        except Exception:
                            pass

                        body_text = self.driver.find_element(By.TAG_NAME, "body").text
                        self.logger.info(f"  -> BODY:\n{body_text[:400]}")
                        body_lower = body_text.lower()

                        import re

                        # CASO 1: Captcha incorrecto → marcar para reintento automático
                        if "incorrecto" in body_lower or "ya utilizado" in body_lower:
                            results[vin] = "ERROR_CAPTCHA_INCORRECTA"
                            dominios[vin] = ""
                            self.logger.warning(f"  !! Captcha incorrecto para VIN {vin}. Se reintentará en próxima corrida.")

                        # CASO 2: Consulta exitosa (la página muestra el dominio)
                        else:
                            # Extraer dominio con el patrón confirmado del portal DNPRA:
                            # "con el dominio AI002LB inscripto en el RRSS..."
                            dominio_match = (
                                re.search(r'con el dominio\s+([A-Z0-9]{4,10})\s+inscripto', body_text) or
                                re.search(r'[Dd]ominio\s*:\s*([A-Z0-9]{4,10})', body_text)
                            )
                            dominio = dominio_match.group(1) if dominio_match else ""
                            dominios[vin] = dominio

                            # Clasificar el resultado
                            if "vencido" in body_lower:
                                results[vin] = "Vencido"
                            elif "vigente" in body_lower:
                                results[vin] = "Vigente"
                            elif dominio:
                                results[vin] = "Encontrado"
                            else:
                                results[vin] = "Consultado"

                            if dominio:
                                self.logger.info(f"  -> Dominio: '{dominio}' | Resultado: {results[vin]}")
                            else:
                                self.logger.warning(f"  -> Sin dominio en respuesta. Resultado: {results[vin]}")

                        consecutive_errors = 0

                    except Exception as ex:
                        self.logger.error(f"  -> Error leyendo resultado: {ex}")
                        results[vin] = "Error Lectura"
                        consecutive_errors += 1

                except (WebDriverException, InvalidSessionIdException, NoSuchWindowException) as e:
                    self.logger.error(f"  !! Sesión caída en VIN {vin}: {type(e).__name__}")
                    results[vin] = "Error de Sesión"
                    consecutive_errors += 1
                    self._reset_driver()

                except Exception as e:
                    self.logger.warning(f"  !! Error en VIN {vin}: {str(e)[:80]}")
                    results[vin] = f"Error: {str(e)[:50]}"
                    consecutive_errors += 1
                    try:
                        error_img = os.path.join(self.project_root, "data", f"error_{vin}.png")
                        self.driver.save_screenshot(error_img)
                    except Exception:
                        pass

                # Guardado periódico cada 5 VINs
                if (i + 1) % 5 == 0 or (i + 1) == len(vins):
                    self.logger.info(f"  Guardando progreso ({i+1}/{len(vins)})...")
                    self.data_handler.save_results(results, dominios)
                    results = {}
                    dominios = {}

                # Frenado de seguridad
                if consecutive_errors >= 10:
                    self.logger.error("10 errores consecutivos. Abortando para proteger el Excel.")
                    break

            self.logger.info("Scraping masivo finalizado.")

        except Exception as e:
            self.logger.error(f"Error crítico: {str(e)}", exc_info=True)
            raise
        finally:
            self.close()

    def solve_captcha_step(self, image_xpath, input_xpath, max_retries=5):
        """
        Resuelve el captcha usando JavaScript puro para localizar y extraer la imagen.
        Evita XPath sobre el src base64 (que crashea Chrome por su tamaño).
        """
        import base64
        captcha_path = os.path.join(self.project_root, "data", "temp_captcha.png")

        for attempt in range(max_retries):
            try:
                time.sleep(1)

                # Extraer captcha con JS puro: busca la imagen con src base64 más grande.
                # Esto evita que Selenium evalúe XPath sobre atributos de src enormes.
                img_src = self.driver.execute_script("""
                    var imgs = document.querySelectorAll('img');
                    var best = null;
                    var bestLen = 0;
                    for (var i = 0; i < imgs.length; i++) {
                        var src = imgs[i].src || '';
                        if (src.startsWith('data:image') && src.length > bestLen) {
                            best = src;
                            bestLen = src.length;
                        }
                    }
                    return best;
                """)

                if not img_src:
                    self.logger.warning(f"  Captcha no encontrado aún (intento {attempt+1}/{max_retries}). Esperando...")
                    time.sleep(3)
                    continue

                # Decodificar base64 y guardar la imagen
                _, b64_data = img_src.split(",", 1)
                img_bytes = base64.b64decode(b64_data)
                with open(captcha_path, "wb") as f:
                    f.write(img_bytes)
                self.logger.info(f"  -> Captcha guardado ({len(img_bytes)} bytes).")

                # Resolver con Gemini/EasyOCR
                resultado = self.captcha_breaker.solve(captcha_path)

                if resultado and len(resultado) >= 3:
                    # Escribir en el campo del captcha via JS también (más estable)
                    self.driver.execute_script(
                        "document.querySelector('input[name=\"verificador\"]').value = arguments[0];",
                        resultado
                    )
                    self.logger.info(f"  -> Captcha resuelto: '{resultado}'")
                    return True

                self.logger.warning(f"  Captcha ilegible '{resultado}' (intento {attempt+1}/{max_retries}).")
                time.sleep(1)

            except Exception as e:
                self.logger.error(f"  Error en captcha paso {attempt+1}: {type(e).__name__}: {str(e)[:80]}")
                time.sleep(2)

        return False


    def close(self):
        """Cierre seguro de recursos."""
        if self.driver:
            try:
                self.logger.info("Cerrando el navegador.")
                self.driver.quit()
            except Exception:
                pass
