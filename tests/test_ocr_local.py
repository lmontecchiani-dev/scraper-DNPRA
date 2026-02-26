import os
import sys

# Añadir raíz al path para poder importar módulos de src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.utils.captcha_breaker import CaptchaBreaker

def test_local_captcha_resolution():
    """
    Script de prueba manual para validar que la limpieza de imagen (OpenCV) 
    y la lectura del texto (Tesseract) funcionan correctamente antes de 
    integrarlos al flujo en vivo de Selenium.
    """
    # IMPORTANTE: Asegúrate de que esta ruta apunte a tu ejecutable de Tesseract real
    # Por defecto en Windows suele ser esta ruta.
    TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    
    print("--- Iniciando Prueba de Captcha OCR Local ---")
    
    try:
        breaker = CaptchaBreaker(tesseract_cmd_path=TESSERACT_PATH)
    except Exception as e:
        print(f"Error inicializando CaptchaBreaker: {e}")
        print("¿Está instalado Tesseract y proporcionaste la ruta correcta?")
        return

    # Ruta a la imagen de prueba. 
    # Debes poner una captura del captcha y llamarla 'test_captcha.png' adentro de la carpeta 'data'.
    test_image_path = os.path.join(project_root, "data", "test_captcha.png")
    
    if not os.path.exists(test_image_path):
        print(f"❌ Error: No se encontró la imagen de prueba en {test_image_path}")
        print("Por favor, guarda un recorte de la imagen del captcha en esa ruta e intenta de nuevo.")
        return
        
    print(f"Procesando imagen: {test_image_path}")
    resultado = breaker.solve(test_image_path)
    
    print("\n" + "="*40)
    if resultado:
        print(f"✅ RESULTADO DEL OCR: '{resultado}'")
        print("Verifica si coincide con los números de la imagen.")
        print(f"Puedes ver la imagen limpiada en: data/test_captcha_processed.png")
    else:
        print("❌ El OCR falló en leer la imagen o devolvió vacío.")
    print("="*40 + "\n")

if __name__ == "__main__":
    test_local_captcha_resolution()
