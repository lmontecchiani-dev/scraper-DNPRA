import sys, os
sys.path.append(r'c:\Users\analistapi\Desktop\Proyectos\scraper-DNPRA')
import cv2
import easyocr
import warnings
warnings.filterwarnings('ignore')

reader = easyocr.Reader(['en'], gpu=False, verbose=False)

data_dir = r'c:\Users\analistapi\Desktop\Proyectos\scraper-DNPRA\data'
imagenes = [
    ('image.png', '99459'),
    ('image copy.png', '36385'),
    ('image copy 2.png', '36385'),
    ('test_captcha.png', '05466'),
]

def run_ocr(img, params):
    r = reader.readtext(img, allowlist='0123456789', detail=0, **params)
    return ''.join(r).strip() if r else ''

def clahe(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    c = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4,4))
    return c.apply(g)

configs = {
    'Raw m3': (lambda i: i, {'mag_ratio': 3.0}),
    'Gray m3': (lambda i: cv2.cvtColor(i, cv2.COLOR_BGR2GRAY), {'mag_ratio': 3.0}),
    'CLAHE m3': (lambda i: clahe(i), {'mag_ratio': 3.0}),
    'CLAHE m4': (lambda i: clahe(i), {'mag_ratio': 4.0}),
    'Inv m3': (lambda i: cv2.bitwise_not(cv2.cvtColor(i, cv2.COLOR_BGR2GRAY)), {'mag_ratio': 3.0}),
}

for img_name, real in imagenes:
    path = os.path.join(data_dir, img_name)
    img = cv2.imread(path)
    print(f'--- {img_name} (Real: {real}) ---')
    for cname, (prep, params) in configs.items():
        processed = prep(img)
        result = run_ocr(processed, params)
        ok = 'OK' if result == real else 'X'
        print(f'  {cname:<10} -> {result:<10} [{ok}]')
    print()
