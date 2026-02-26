import os
import sys
import glob
import time

# Añadir raíz al path para poder importar módulos de src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.utils.captcha_breaker import CaptchaBreaker

def test_masivo():
    """
    Prueba masiva de CAPTCHAs.
    Busca TODAS las imágenes .png en la carpeta data/ y las procesa con EasyOCR.
    
    USO:
      1. Guardá varios recortes de captchas en data/ como:
         captcha1.png, captcha2.png, captcha3.png, etc.
      2. Ejecutá:
         .\.venv\Scripts\python.exe tests\test_ocr_masivo.py
    """
    TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    
    print("=" * 60)
    print("  🧠 TEST MASIVO DE OCR - EasyOCR + Tesseract")
    print("=" * 60)
    
    # Inicializar el motor UNA sola vez (cargar modelo a RAM)
    print("\n⏳ Cargando modelo de IA... (solo la primera vez demora)")
    breaker = CaptchaBreaker(tesseract_cmd_path=TESSERACT_PATH)
    print("✅ Modelo cargado.\n")
    
    # Buscar todas las imágenes PNG en data/
    data_dir = os.path.join(project_root, "data")
    imagenes = sorted(glob.glob(os.path.join(data_dir, "*.png")))
    
    # Excluir las imágenes procesadas (_processed)
    imagenes = [img for img in imagenes if "_processed" not in img]
    
    if not imagenes:
        print(f"❌ No se encontraron imágenes .png en {data_dir}")
        print("   Guardá captchas como: captcha1.png, captcha2.png, etc.")
        return
    
    print(f"📂 Encontradas {len(imagenes)} imagen(es) en data/\n")
    print("-" * 60)
    print(f"{'#':<4} {'Archivo':<30} {'Resultado':<15} {'Tiempo'}")
    print("-" * 60)
    
    resultados = []
    
    for i, img_path in enumerate(imagenes, 1):
        nombre = os.path.basename(img_path)
        inicio = time.time()
        
        texto = breaker.solve(img_path)
        
        duracion = time.time() - inicio
        
        estado = texto if texto else "(vacío)"
        resultados.append((nombre, estado, duracion))
        
        print(f"{i:<4} {nombre:<30} {estado:<15} {duracion:.2f}s")
        
        # Respetar el Rate Limit gratuito de Gemini (15 RPM = 4 segundos de espera)
        if i < len(imagenes):
            try:
                time.sleep(4.2)
            except KeyboardInterrupt:
                print("\n⚠️ Test cancelado por el usuario.")
                break
    
    print("-" * 60)
    print(f"\n📊 Resumen: {len(resultados)} imágenes procesadas")
    
    exitosas = sum(1 for _, r, _ in resultados if r != "(vacío)")
    print(f"   ✅ Extracciones exitosas: {exitosas}/{len(resultados)}")
    print(f"   ⏱️  Tiempo promedio: {sum(t for _, _, t in resultados) / len(resultados):.2f}s")
    
    print("\n💡 Compará cada resultado con la imagen original en data/")
    print("   Si alguno falló, ese captcha probablemente necesitaría un refresco en producción.\n")

if __name__ == "__main__":
    test_masivo()
