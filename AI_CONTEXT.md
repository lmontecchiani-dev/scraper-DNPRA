# AI_CONTEXT.md

## 1. Project Overview

- **Name**: scraper-DNPRA
- **Objective**: Sistema de automatización y web scraping para la recolección de datos de DNPRA.
- **Description**: Sistema de web scraping y automatización de datos con arquitectura modular "Code-First" orientada a ambientes productivos desatendidos.

## 2. Project Structure

El proyecto sigue una arquitectura modular estricta para garantizar escalabilidad:

- `src/`: Lógica productiva core (scrapers, transformaciones ETL, pipelines de sincronización).
- `config/`: Archivos `.yaml` centralizando parámetros, URLs y selectores web.
- `scripts/`: Scripts `.bat` o `.ps1` para utilidades, limpieza y tareas programadas.
- `tests/`: Pruebas automatizadas (unitarias e integración) usando `pytest`.
- `docs/`: Reglas de negocio y manuales operativos.
- `logs/`: Archivos `.log` de ejecución y trazabilidad de errores.
- `data/`: Inputs/outputs locales, temporales, CSVs y backups.
- `credentials/`: Claves y secretos. Oculto por `.gitignore`.

## 3. Technology Stack

- **Runtime**: Python 3.10+
- **Scraping Engine**: Selenium + webdriver-manager
- **OCR**: EasyOCR (Local CPU), Gemini 2.0 Flash (IA API)
- **Data Manipulation**: Pandas, Openpyxl
- **Config Management**: PyYAML, python-dotenv

## 4. Critical Rules (The Ten Commandments)

1. **Configuración sobre Hardcoding:** Todos los selectores de Selenium, rutas y URLs DEBEN residir en `config/mis_ajustes.yaml`.
2. **Validación de Datos**: Antes de procesar, verificar tipo de certificado (Nacional/Importado) leyendo el 4to carácter de la columna `Nro.Fabr.` (1=N, 2=I).
3. **Manejo de Errores y Timeouts Grácil:** Implementar políticas de reintentos, control de `TimeoutExceptions` y esperas explícitas.
4. **Testing Obligatorio**: Antes de alterar la lógica central, verificar consistencia técnica.
5. **No silenciar excepciones**: Registrar stacktrace en log (`logger.error`). Fallar de forma ruidosa en errores críticos.
6. **Manejo de rutas absolutas**: Usar rutas computadas desde la raíz del proyecto para compatibilidad con Task Scheduler.

## 5. Arquitectura de Automatización Final

El sistema opera de forma desatendida y resiliente:

1.  **Capa de Datos (DataHandler)**:
    - Soporte multi-formato (`.xls` SIAC y `.xlsx` procesado).
    - Header dinámico: busca "Chasis" y "Nro.Fabr.".
    - Retry en guardado por archivo bloqueado y creación de backups automáticos.
2.  **Lógica Nacional/Importado**:
    - Antes de cada consulta, lee `Nro.Fabr.`.
    - Si el dígito en índice 3 es '2' → Click en Importado. Caso contrario → Nacional.
3.  **Motor de OCR (Cascada Multi-Nivel)**:
    - **Tier 1 (Nube)**: `gemini-2.0-flash` (IA Nativa) para máxima precisión. Auto-bypass si la cuota se agota.
    - **Tier 2 (Soberanía Local)**: EasyOCR con **16 estrategias de pre-procesamiento** (OTSU, HSV, CLAHE, Bilateral) y sistema de votación.
    - **Validación 5D**: Se exige exactamente 5 dígitos. Si el OCR falla (ej. lee 3 números), el bot clickea en **"Cargar nuevo código"** para refrescar el captcha y reintentar.
4.  **Cierre de Ciclo**:
    - Extrae el Dominio/Patente de la página de resultados vía regex.
    - Guarda en columnas "Resultado DNPRA" y "Dominio DNPRA".
    - Detecta captchas incorrectos y los marca para reintento automático.

## 6. Operación y Mantenimiento

- **Control de Versiones**: Repositorio oficial en [GitHub](https://github.com/lmontecchiani-dev/scraper-DNPRA).
- **Ejecución**: `.\.venv\Scripts\python.exe src/main.py`
- **Estado Actual**: Producción-Ready. Sistema de 5-dígitos con refresco automático implementado el 25/02/2026.
