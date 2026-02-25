# Scraper DNPRA

Scraper automatizado para el portal DNPRA con resolución inteligente de CAPTCHAs usando Inteligencia Artificial local.

## Requisitos Previos

- **Python 3.11** (no la versión de Microsoft Store)
- **Tesseract OCR** instalado en `C:\Program Files\Tesseract-OCR\tesseract.exe`
  - [Descargar desde GitHub](https://github.com/UB-Mannheim/tesseract/wiki)

## Instalación

```powershell
# 1. Crear entorno virtual
python -m venv .venv

# 2. Activar entorno virtual
.\.venv\Scripts\Activate.ps1

# 3. Instalar dependencias
pip install -r requirements.txt
```

> **Nota:** La primera vez que se ejecute el OCR, EasyOCR descargará automáticamente sus modelos de red neuronal (~100MB). Esto solo ocurre una vez.

## Probar el OCR del CAPTCHA

### Paso 1: Obtener una imagen de prueba

1. Entrá a la página del DNPRA donde aparece el CAPTCHA.
2. Usá la **Herramienta de Recorte** (`Win + Shift + S`) para recortar **solo la imagen del CAPTCHA**.
3. Guardá la captura en:

```
data\test_captcha.png
```

### Paso 2: Ejecutar el test

```powershell
.\.venv\Scripts\python.exe tests\test_ocr_local.py
```

### Paso 3: Verificar el resultado

La consola mostrará algo como:

```
--- Iniciando Prueba de Captcha OCR Local ---
Procesando imagen: ...\data\test_captcha.png
========================================
✅ RESULTADO DEL OCR: '85466'
Verifica si coincide con los números de la imagen.
========================================
```

Compará el número impreso con lo que ves en la imagen del CAPTCHA.

### Probar con otra imagen

Simplemente reemplazá `data\test_captcha.png` con una nueva captura y volvé a ejecutar el comando del Paso 2.

## Arquitectura del Motor OCR

El sistema usa una estrategia **Dual-Engine** con fallback automático:

```
Imagen CAPTCHA
      │
      ▼
┌─────────────────────┐
│  EasyOCR (PyTorch)  │  ← Motor primario: Red Neuronal Deep Learning
│  mag_ratio=3.0      │     Lee formas completas incluso con ruido
└─────────┬───────────┘
          │
     ¿Leyó ≥ 3 dígitos?
      │           │
     SÍ          NO
      │           │
      ▼           ▼
   Retorna   ┌──────────────────┐
   el texto  │ Tesseract + OpenCV│ ← Fallback: Limpieza clásica + OCR
             │  threshold=180    │
             └────────┬─────────┘
                      │
                   Retorna lo que pueda
```

## Estructura del Proyecto

```
scraper-DNPRA/
├── config/              # Archivos de configuración YAML
├── data/                # Imágenes de prueba del CAPTCHA
├── src/
│   ├── main.py          # Orquestador principal
│   ├── scraper.py       # Lógica de Selenium
│   └── utils/
│       ├── captcha_breaker.py   # Motor OCR Dual (EasyOCR + Tesseract)
│       └── config_loader.py     # Cargador de configuración
├── tests/
│   └── test_ocr_local.py       # Script de prueba del CAPTCHA
├── requirements.txt
└── README.md
```

## Tech Stack

| Componente        | Tecnología                      |
| ----------------- | ------------------------------- |
| **Scraping**      | Selenium + WebDriver Manager    |
| **OCR Primario**  | EasyOCR (PyTorch Deep Learning) |
| **OCR Fallback**  | Tesseract + OpenCV              |
| **Configuración** | YAML + dotenv                   |
| **Lenguaje**      | Python 3.11                     |
