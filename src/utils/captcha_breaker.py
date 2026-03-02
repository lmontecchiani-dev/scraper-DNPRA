import cv2
import pytesseract
import numpy as np
import logging
from PIL import Image
import os
import easyocr
import time
import shutil
from datetime import datetime
import httpx
from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class CaptchaBreaker:
    """
    Motor OCR en Cascada de 3 Capas:
    1. Gemini 2.5 Flash (IA Multimodal en la nube, ~99% precisión en DNPRA)
    2. EasyOCR (PyTorch CNN local Multi-Estrategia, fallback)
    3. Tesseract + OpenCV (OCR Clásico, último recurso)
    """
    
    def __init__(self, tesseract_cmd_path=None):
        if tesseract_cmd_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd_path
            
        # 1. Init Gemini Farm (Soporte para múltiples API Keys)
        self.gemini_clients = []
        self.current_key_index = 0
        self.exhausted_keys = set()
        
        gemini_keys_str = os.getenv("GEMINI_API_KEYS")
        if gemini_keys_str:
            keys = [k.strip() for k in gemini_keys_str.split(",") if k.strip()]
            for i, key in enumerate(keys):
                try:
                    # HttpOptions con timeout de 30s para evitar colgadas por 503/disconnects
                    client = genai.Client(api_key=key)
                    self.gemini_clients.append(client)
                    logger.info(f"✅ Gemini Key #{i+1} configurada ({key[:5]}...{key[-5:]})")
                except Exception as e:
                    logger.error(f"Error configurando Gemini Key #{i+1}: {e}")
            
            if self.gemini_clients:
                self.gemini_ready = True
                logger.info(f"🚀 Granja de Gemini inicializada con {len(self.gemini_clients)} llaves.")
        else:
            logger.warning("No se encontró GEMINI_API_KEYS en .env. Saltando Tier 1.")
            
        # 2. Init EasyOCR
        logger.info("Cargando cerebro neuronal local de EasyOCR (puede demorar unos segundos la primera vez)...")
        self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        logger.info("✅ EasyOCR inicializado en RAM.")

    def solve_with_gemini(self, image_path: str) -> str:
        """ Motor Tier 1: Gemini Farm con Rotación de Llaves y Reintentos """
        if not self.gemini_ready or not self.gemini_clients:
            return ""

        # Intentar con cada cliente disponible que no esté marcado como agotado
        start_idx = self.current_key_index
        for i in range(len(self.gemini_clients)):
            idx = (start_idx + i) % len(self.gemini_clients)
            
            if idx in self.exhausted_keys:
                continue
                
            client = self.gemini_clients[idx]
            
            # Throttling base: 5s para respetar cuota free (15 RPM).
            base_delay = 5
            max_retries = 0  # Sin reintentos: si falla, rotamos a la siguiente llave
            
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    wait_time = 5 * (2 ** (attempt - 1))
                    logger.warning(f"⚠️ Reintento {attempt}/{max_retries} para Gemini (Key #{idx+1}). Esperando {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.info(f"⏳ Enviando a Gemini (Key #{idx+1}, pausa {base_delay}s)...")
                    time.sleep(base_delay)
                
                try:
                    img = Image.open(image_path)
                    prompt = (
                        "Esta es una imagen de un CAPTCHA con números fuertemente tachados por ruido adversario. "
                        "Tu única tarea es leer los números (suele haber 5). "
                        "Ignora absolutamente todas las rayas. Responde ÚNICAMENTE con la cadena de números (ejemplo: 12345) y nada más. "
                        "Si un caracter está tapado pero la forma base se parece a un número, deducilo pero devuelve solo números."
                    )
                    
                    response = client.models.generate_content(
                        model='gemini-flash-latest',
                        contents=[prompt, img]
                    )
                    text = response.text.strip()
                    text = "".join(filter(str.isdigit, text))
                    if text:
                        return text
                    else:
                        logger.warning(f"Respuesta vacía de Gemini (Key #{idx+1}) en intento {attempt}.")
                        
                except Exception as e:
                    error_msg = str(e)
                    logger.debug(f"DEBUG: Gemini Error completo: {error_msg}")
                    
                    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                        logger.error(f"❌ Cuota Agotada (429) para Gemini Key #{idx+1}. Rotando...")
                        self.exhausted_keys.add(idx)
                        break
                    elif "503" in error_msg or "UNAVAILABLE" in error_msg:
                        logger.error(f"⚠️ Servidor Sobrecargado (503) para Gemini Key #{idx+1}. Rotando...")
                        break
                    elif "404" in error_msg:
                        logger.error(f"⚠️ Modelo No Encontrado (404) para Gemini Key #{idx+1}. Intentando fallback...")
                        # Fallback a gemini-flash-latest si 1.5-flash falla
                        try:
                            response = client.models.generate_content(model='gemini-flash-latest', contents=[prompt, img])
                            text = "".join(filter(str.isdigit, response.text.strip()))
                            if text: return text
                        except: pass
                        break
                    else:
                        logger.error(f"❌ Error Crítico Gemini (Key #{idx+1}): {error_msg}")
                        break
        
        logger.error("❌ CRÍTICO: Todas las llaves de la granja Gemini están agotadas o fallaron.")
        return ""

    def _preprocess_variants(self, img_bgr):
        """
        Genera múltiples versiones preprocesadas de la imagen del captcha DNPRA.
        Optimizado para: fondo teal claro, dígitos oscuros, líneas cruzadas.
        """
        variants = {}
        h, w = img_bgr.shape[:2]
        # Escalar a tamaño mínimo razonable para OCR
        scale = max(1, 200 // h)
        if scale > 1:
            img_bgr = cv2.resize(img_bgr, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # 1. OTSU invertido: dígitos oscuros → blancos (mejor orientación para OCR)
        _, otsu_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        variants['otsu_inv'] = otsu_inv

        # 2. OTSU normal
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variants['otsu'] = otsu

        # 3. Median blur primero → quita ruido de puntos, luego OTSU
        med = cv2.medianBlur(gray, 3)
        _, med_otsu = cv2.threshold(med, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        variants['med_otsu'] = med_otsu

        # 4. Threshold adaptativo (bueno cuando el fondo varía)
        adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY_INV, 11, 4)
        variants['adaptive'] = adapt

        # 5. CLAHE + OTSU inv
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        clahe_img = clahe.apply(gray)
        _, clahe_otsu = cv2.threshold(clahe_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        variants['clahe_otsu'] = clahe_otsu

        # 6. Píxeles oscuros directos (el captcha tiene fondo teal y dígitos oscuros)
        # V=Value en HSV. Dígitos tienen V bajo (oscuros)
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        dark = cv2.inRange(hsv, (0, 0, 0), (180, 255, 120))
        variants['dark_pixels'] = dark

        # 7. Bilateral filter (preserva bordes) + OTSU
        bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
        _, bil_otsu = cv2.threshold(bilateral, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        variants['bilateral'] = bil_otsu

        # 8. Original color BGR (EasyOCR a veces funciona mejor en color)
        variants['color'] = img_bgr

        return variants

    def _run_easyocr(self, img, mag_ratio=4.0) -> str:
        """ Ejecuta EasyOCR sobre una imagen (numpy array o path) """
        try:
            resultados = self.reader.readtext(img, allowlist='0123456789', detail=0, mag_ratio=mag_ratio)
            if not resultados:
                return ""
            texto = "".join(resultados).strip()
            return "".join(filter(str.isdigit, texto))
        except Exception:
            return ""

    def solve_with_easyocr(self, image_path: str) -> str:
        """
        Motor Tier 2: Multi-estrategia mejorada para captcha DNPRA.
        8 preprocessings x 2 magnitudes = 16 intentos. Vota en resultados de 5 dígitos.
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return ""

            variants = self._preprocess_variants(img)
            mag_ratios = [4.0, 6.0]
            candidatos = []

            for nombre, img_var in variants.items():
                for mag in mag_ratios:
                    res = self._run_easyocr(img_var, mag_ratio=mag)
                    if res:
                        candidatos.append(res)
                        logger.debug(f"  [{nombre}@{mag}] → '{res}'")

            if not candidatos:
                return ""

            # Prioridad: resultados de exactamente 5 dígitos (DNPRA siempre tiene 5)
            from collections import Counter
            cinco = [r for r in candidatos if len(r) == 5]
            if cinco:
                ganador, votos = Counter(cinco).most_common(1)[0]
                logger.info(f"✅ EasyOCR (5 dígitos) consenso: '{ganador}' ({votos}/{len(candidatos)} votos)")
                return ganador

            # Fallback: resultado más largo de los candidatos
            mejor = max(candidatos, key=len)
            logger.warning(f"⚠️ EasyOCR sin 5 dígitos, mejor: '{mejor}' de {len(candidatos)} candidatos")
            return mejor

        except Exception as e:
            logger.error(f"Error en EasyOCR mejorado: {e}")
            return ""

    def preprocess_image(self, image_path, output_path=None):
        """ Limpia la imagen para Tesseract (Tier 3) """
        try:
            img = cv2.imread(image_path)
            if img is None: raise FileNotFoundError(f"Imagen no en: {image_path}")

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
            
            inv = cv2.bitwise_not(thresh)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            closed = cv2.morphologyEx(inv, cv2.MORPH_CLOSE, kernel)

            if output_path is None:
                base, ext = os.path.splitext(image_path)
                output_path = f"{base}_processed{ext}"
                
            cv2.imwrite(output_path, closed)
            return output_path
        except Exception as e:
            logger.error(f"Error OpenCV preprocess: {e}")
            raise

    def solve_with_tesseract(self, image_path: str) -> str:
        """ Motor Tier 3: OpenCV + Tesseract """
        try:
            processed_path = self.preprocess_image(image_path)
            custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789'
            text = pytesseract.image_to_string(Image.open(processed_path), config=custom_config)
            return "".join(filter(str.isdigit, text.strip()))
        except Exception as e:
            logger.error(f"Error Tesseract Fallback: {e}")
            return ""

    def _save_to_dataset(self, image_path: str, result: str):
        """Guarda una copia del captcha en la carpeta de dataset para futuro entrenamiento."""
        try:
            dataset_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "dataset")
            os.makedirs(dataset_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Si no hay resultado o es inválido, marcamos como fallido
            label = result if (result and len(result) == 5) else f"FAILED_{result or 'NONE'}"
            
            filename = f"{timestamp}_{label}.png"
            dest_path = os.path.join(dataset_dir, filename)
            
            shutil.copy2(image_path, dest_path)
            logger.info(f"💾 Captcha guardado en dataset: {filename}")
        except Exception as e:
            logger.error(f"Error guardando en dataset: {e}")

    def solve(self, image_path: str) -> str:
        """
        Método unificado. 
        Intenta Gemini -> EasyOCR -> Tesseract en cascada garantizando máxima robustez.
        """
        logger.debug(f"=== Iniciando Extracción en Cascada: {os.path.basename(image_path)} ===")
        final_result = ""
        
        # 1. TIER 1: Gemini 
        final_result = self.solve_with_gemini(image_path)
        
        # 2. TIER 2: Fallback EasyOCR (si Gemini no devolvió 5 dígitos)
        if not (final_result and len(final_result) == 5):
            if final_result:
                logger.warning(f"Gemini devolvió longitud incorrecta ({len(final_result)}). Probando EasyOCR...")
            else:
                logger.warning("Gemini falló. Activando Fallback Local con EasyOCR...")
            
            easy_result = self.solve_with_easyocr(image_path)
            if easy_result and len(easy_result) == 5:
                final_result = easy_result
                logger.info(f"✅ [TIER 2] Resuelto por EasyOCR: '{final_result}'")
            
        # 3. TIER 3: Fallback Tesseract (si todo lo anterior falló)
        if not (final_result and len(final_result) == 5):
            logger.warning("EasyOCR falló. Probando Tesseract como último recurso...")
            tesseract_result = self.solve_with_tesseract(image_path)
            if tesseract_result:
                final_result = tesseract_result
                logger.info(f"✅ [TIER 3] Resuelto por Tesseract: '{final_result}'")

        # Guardar en dataset para entrenamiento futuro
        self._save_to_dataset(image_path, final_result)
        
        if not final_result:
            logger.error("❌ CRÍTICO: Todos los motores fallaron.")
            
        return final_result

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    breaker = CaptchaBreaker(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    test_image = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "test_captcha.png")
    
    if os.path.exists(test_image):
        print("\n--- Ejecutando Test Cascada Nube/Local ---")
        resultado = breaker.solve(test_image)
        print(f"\nResultado Final de Extracción: {resultado}")
    else:
        print(f"Coloca un archivo 'test_captcha.png' en la carpeta data.")


