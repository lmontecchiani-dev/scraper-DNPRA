"""
Test de eliminacion de lineas con Hough Transform + EasyOCR.
Detecta las rayas diagonales del CAPTCHA y las borra antes de leer.
"""
import sys, os, glob
sys.path.append(r'c:\Users\analistapi\Desktop\Proyectos\scraper-DNPRA')
import cv2
import numpy as np
import easyocr
import warnings
warnings.filterwarnings('ignore')

reader = easyocr.Reader(['en'], gpu=False, verbose=False)

def remove_lines(img):
    """Detecta lineas con Hough y las pinta con el color del fondo."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Detectar bordes
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    # Detectar lineas con HoughLinesP
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=20, maxLineGap=5)
    
    clean = img.copy()
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # Calcular largo de la linea
            length = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            # Solo borrar lineas largas (las rayas, no los trazos de los numeros)
            if length > 25:
                # Pintar con blanco (color de fondo del CAPTCHA)
                cv2.line(clean, (x1, y1), (x2, y2), (255, 255, 255), 3)
    
    return clean

def remove_lines_v2(img):
    """Version 2: Usa inpainting para rellenar las lineas de forma natural."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=25, maxLineGap=5)
    
    # Crear mascara con las lineas detectadas
    mask = np.zeros(gray.shape, dtype=np.uint8)
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = np.sqrt((x2-x1)**2 + (y2-y1)**2) 
            if length > 25:
                cv2.line(mask, (x1, y1), (x2, y2), 255, 3)
    
    # Inpainting: rellena las areas de la mascara con el contexto circundante
    clean = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)
    return clean

def run_ocr(img):
    r = reader.readtext(img, allowlist='0123456789', detail=0, mag_ratio=3.0)
    return ''.join(r).strip() if r else ''

def run_ocr_detail(img):
    """Version con detalle para ver confianza."""
    r = reader.readtext(img, allowlist='0123456789', detail=1, mag_ratio=3.0)
    if not r:
        return '', 0.0
    text = ''.join([item[1] for item in r])
    conf = sum([item[2] for item in r]) / len(r)
    return text, conf

# ---- MAIN ----
data_dir = r'c:\Users\analistapi\Desktop\Proyectos\scraper-DNPRA\data'
imagenes = sorted(glob.glob(os.path.join(data_dir, '*.png')))
imagenes = [i for i in imagenes if '_processed' not in i and '_clean' not in i]

reales = {
    'image.png': '99459',
    'image copy.png': '36385', 
    'image copy 2.png': '36385',
    'test_captcha.png': '05466',
}

print("=" * 65)
print("  TEST: Hough Line Removal + EasyOCR")
print("=" * 65)

for img_path in imagenes:
    nombre = os.path.basename(img_path)
    real = reales.get(nombre, '?????')
    img = cv2.imread(img_path)
    
    print(f"\n--- {nombre} (Real: {real}) ---")
    
    # 1. Sin limpiar (baseline)
    r1 = run_ocr(img)
    ok1 = 'OK' if r1 == real else 'X'
    
    # 2. Con Hough + pintar blanco
    clean1 = remove_lines(img)
    r2 = run_ocr(clean1)
    ok2 = 'OK' if r2 == real else 'X'
    
    # 3. Con Hough + inpainting
    clean2 = remove_lines_v2(img)
    r3 = run_ocr(clean2)
    ok3 = 'OK' if r3 == real else 'X'
    
    # 4. Inpainting + Grayscale
    gray_clean = cv2.cvtColor(clean2, cv2.COLOR_BGR2GRAY)
    r4 = run_ocr(gray_clean)
    ok4 = 'OK' if r4 == real else 'X'
    
    # 5. Inpainting + CLAHE
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4,4))
    clahe_clean = clahe.apply(gray_clean)
    r5 = run_ocr(clahe_clean)
    ok5 = 'OK' if r5 == real else 'X'
    
    print(f"  Raw          -> {r1:<10} [{ok1}]")
    print(f"  Hough+White  -> {r2:<10} [{ok2}]")
    print(f"  Hough+Inpnt  -> {r3:<10} [{ok3}]")
    print(f"  Inpnt+Gray   -> {r4:<10} [{ok4}]")
    print(f"  Inpnt+CLAHE  -> {r5:<10} [{ok5}]")
    
    # Guardar la version limpia para debug visual
    cv2.imwrite(os.path.join(data_dir, f"{os.path.splitext(nombre)[0]}_clean.png"), clean2)

print("\n" + "=" * 65)
print("  Imagenes limpias guardadas en data/*_clean.png")
print("=" * 65)
