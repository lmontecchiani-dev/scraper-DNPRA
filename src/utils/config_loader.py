import os
import yaml
from dotenv import load_dotenv

def load_config(config_path="config/mis_ajustes.yaml"):
    """
    Carga de forma segura las configuraciones en YAML y las credenciales del .env
    """
    # Cargar variables de entorno del archivo .env
    load_dotenv()
    
    # Cargar el archivo de configuración YAML
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"No se encontró el archivo de configuración: {config_path}")
        
    with open(config_path, "r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
        
    return config

# Ejemplo de uso interno (para pruebas rápidas)
if __name__ == "__main__":
    conf = load_config()
    print("Configuración cargada exitosamente.")
