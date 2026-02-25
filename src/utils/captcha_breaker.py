import cv2
import pytesseract
import numpy as np
import logging
from PIL import Image
import os
import easyocr
import time
from google import genai
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
            
        # 1. Init Gemini (Nuevo SDK oficial google.genai)
        self.gemini_ready = False
        self.gemini_client = None
        self.gemini_quota_failed = 0  # Contador de fallos 429 consecutivos
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                self.gemini_client = genai.Client(
                    api_key=gemini_key
                )
                self.gemini_ready = True
                logger.info("✅ Gemini API (SDK Moderno) configurada exitosamente.")
            except Exception as e:
                logger.error(f"Error configurando Gemini: {e}")
        else:
            logger.warning("No se encontró GEMINI_API_KEY en .env. Saltando Tier 1.")
            
        # 2. Init EasyOCR
        logger.info("Cargando cerebro neuronal local de EasyOCR (puede demorar unos segundos la primera vez)...")
        self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        logger.info("✅ EasyOCR inicializado en RAM.")

    def solve_with_gemini(self, image_path: str) -> str:
        """ Motor Tier 1: Gemini en la Nube (API Nativa) con Reintentos y Backoff """
        # Si ya sabemos que Gemini está quota-bloqueado, saltar directamente a EasyOCR
        if not self.gemini_ready or not self.gemini_client:
            return ""
        if self.gemini_quota_failed >= 3:
            logger.info("⏭️ Gemini quota agotada. Usando EasyOCR directo...")
            return ""
        
        # Throttling base: 2s para no saturar la API en uso normal.
        # Se hace backoff exponencial solo cuando hay errores 429.
        base_delay = 2
        max_retries = 2
        
        for attempt in range(max_retries + 1):
            if attempt > 0:
                wait_time = 5 * (2 ** (attempt - 1))  # Backoff: 5s, 10s
                logger.warning(f"⚠️ Reintento {attempt}/{max_retries} para Gemini. Esperando {wait_time}s...")
                time.sleep(wait_time)
            else:
                logger.info(f"⏳ Enviando a Gemini (pausa {base_delay}s)...")
                time.sleep(base_delay)

                
            try:
                img = Image.open(image_path)
                prompt = (
                    "Esta es una imagen de un CAPTCHA con números fuertemente tachados por ruido adversario. "
                    "Tu única tarea es leer los números (suele haber 5). "
                    "Ignora absolutamente todas las rayas. Responde ÚNICAMENTE con la cadena de números (ejemplo: 12345) y nada más. "
                    "Si un caracter está tapado pero la forma base se parece a un número, deducilo pero devuelve solo números."
                )
                
                target_model = 'gemini-2.0-flash'  # Verificado disponible en el entorno
                
                response = self.gemini_client.models.generate_content(
                    model=target_model,
                    contents=[prompt, img]
                )
                text = response.text.strip()
                text = "".join(filter(str.isdigit, text))
                if text:
                    return text
                else:
                    logger.warning(f"Respuesta vacía de Gemini en intento {attempt}. Reintentando...")
                    
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    self.gemini_quota_failed += 1
                    logger.error(f"❌ Error de Cuota (429) en intento {attempt} (total fallos: {self.gemini_quota_failed}).")
                    if attempt == max_retries:
                        logger.error("Se agotaron los reintentos para Gemini.")
                else:
                    logger.error(f"Error inesperado en Gemini API (Intento {attempt}): {e}")
                    break
        
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

    def solve(self, image_path: str) -> str:
        """
        Método unificado. 
        Intenta Gemini -> EasyOCR -> Tesseract en cascada garantizando máxima robustez.
        """
        logger.debug(f"=== Iniciando Extracción en Cascada: {os.path.basename(image_path)} ===")
        
        # 1. TIER 1: Gemini 2.0 Flash
        gemini_result = self.solve_with_gemini(image_path)
        if gemini_result and len(gemini_result) >= 3:
            logger.info(f"✅ [TIER 1 - Nube] DNPRA CAPTCHA resuelto por Gemini 2.0: '{gemini_result}'")
            return gemini_result
            
        logger.warning(f"Gemini falló o devolvió vacío (Res: '{gemini_result}'). Activando Fallback Local...")
        
        # 2. TIER 2: EasyOCR Multi-Estrategia
        easy_result = self.solve_with_easyocr(image_path)
        if easy_result and len(easy_result) >= 3:
            logger.info(f"✅ [TIER 2 - Local DL] DNPRA CAPTCHA resuelto por EasyOCR: '{easy_result}'")
            return easy_result
            
        logger.warning(f"EasyOCR no extrajo 5 digitos (Res: '{easy_result}'). Activando último recurso Tesseract...")
        
        # 3. TIER 3: Tesseract
        tesseract_result = self.solve_with_tesseract(image_path)
        if tesseract_result:
            logger.info(f"✅ [TIER 3 - Classic OCR] DNPRA CAPTCHA resuelto por Tesseract: '{tesseract_result}'")
            return tesseract_result
            
        logger.error("❌ CRÍTICO: Los 3 motores (Gemini, EasyOCR, Tesseract) fallaron al extraer el texto.")
        return ""

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


