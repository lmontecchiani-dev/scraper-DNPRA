import os
import sys
import logging
from datetime import datetime

# Añadir el raíz del proyecto al sys.path asumiendo que el script se ejecuta desde ahí
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from src.utils.config_loader import load_config
from src.scraper import DnpraScraper

def setup_logging():
    """Configura el sistema de logs general orientado al entorno productivo."""
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"ejecucion_{datetime.now().strftime('%Y%m%d')}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("Main")

def main():
    logger = setup_logging()
    logger.info("Iniciando proceso de scraping DNPRA...")
    
    try:
        # 1. Cargar Configuración Central
        config_path = os.path.join(project_root, "config", "mis_ajustes.yaml")
        config = load_config(config_path)
        logger.info("Configuración cargada correctamente.")
        
        # 2. Inicializar y correr Scraper
        scraper = DnpraScraper(config)
        scraper.start_scraping()
        
        # 3. Futuro: Transformación y Sincronización (ETL)
        logger.info("Proceso finalizado con éxito.")
        
    except Exception as e:
        logger.critical("El proceso abortó debido a un error no manejado.", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
