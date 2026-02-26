"""
Test: Bilateral Filter + Confidence Scoring + Multiple mag_ratios
"""
import sys, os, glob
sys.path.append(r'c:\Users\analistapi\Desktop\Proyectos\scraper-DNPRA')
import cv2
import numpy as np
import easyocr
import warnings
warnings.filterwarnings('ignore')

reader = easyocr.Reader(['en'], gpu=False, verbose=False)

data_dir = r'c:\Users\analistapi\Desktop\Proyectos\scraper-DNPRA\data'

reales = {
    'image.png': '99459',
    'image copy.png': '36385',
    'image copy 2.png': '36385',
    'image copy 3.png': '68534',
    'image copy 4.png': '09233',
    'image copy 5.png': '47258',
    'image copy 6.png': '95942',
    'test_captcha.png': '05466',
}

def ocr(img, mag=3.0):
    r = reader.readtext(img, allowlist='0123456789', detail=1, mag_ratio=mag)
    if not r:
        return '', 0.0
    text = ''.join(c[1] for c in r)
    text = ''.join(filter(str.isdigit, text))
    conf = sum(c[2] for c in r) / len(r)
    return text, round(conf, 2)

def bilateral(img):
    return cv2.bilateralFilter(img, 9, 75, 75)

def sharp(img):
    kernel = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]])
    return cv2.filter2D(img, -1, kernel)

imagenes = sorted(glob.glob(os.path.join(data_dir, '*.png')))
imagenes = [i for i in imagenes if '_processed' not in i and '_clean' not in i]

strategies = [
    ('Raw m3',       lambda i: i, 3.0),
    ('Raw m2',       lambda i: i, 2.0),
    ('Raw m4',       lambda i: i, 4.0),
    ('Gray m3',      lambda i: cv2.cvtColor(i, cv2.COLOR_BGR2GRAY), 3.0),
    ('Bilat m3',     lambda i: bilateral(i), 3.0),
    ('Bilat+G m3',   lambda i: cv2.cvtColor(bilateral(i), cv2.COLOR_BGR2GRAY), 3.0),
    ('Sharp m3',     lambda i: sharp(i), 3.0),
    ('Sharp+G m3',   lambda i: cv2.cvtColor(sharp(i), cv2.COLOR_BGR2GRAY), 3.0),
    ('Bilat+S m3',   lambda i: sharp(bilateral(i)), 3.0),
]

# Track best strategy per image
best_counts = {s[0]: 0 for s in strategies}

for img_path in imagenes:
    nombre = os.path.basename(img_path)
    real = reales.get(nombre, '?')
    img = cv2.imread(img_path)
    print(f'--- {nombre} (Real: {real}) ---')
    
    best_text = ''
    best_conf = 0
    best_strat = ''
    
    for sname, prep, mag in strategies:
        processed = prep(img)
        text, conf = ocr(processed, mag)
        ok = 'OK' if text == real else ' '
        print(f'  {sname:<12} -> {text:<10} conf={conf:.2f} [{ok}]')
        
        # Track the best 5-digit result by confidence
        if len(text) == 5 and conf > best_conf:
            best_conf = conf
            best_text = text
            best_strat = sname
        elif not best_text and len(text) >= 3 and conf > best_conf:
            best_conf = conf
            best_text = text
            best_strat = sname
    
    match = 'OK' if best_text == real else 'X'
    print(f'  >> ELEGIDO: {best_text} ({best_strat}, conf={best_conf:.2f}) [{match}]')
    if best_strat:
        best_counts[best_strat] = best_counts.get(best_strat, 0) + 1
    print()

print('=== Resumen por estrategia ===')
for s, c in sorted(best_counts.items(), key=lambda x: -x[1]):
    if c > 0:
        print(f'  {s}: elegido {c} veces')
