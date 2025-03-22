#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import sys
import datetime
import json

# Cargar variables de entorno
load_dotenv()

# Se asume que ya tienes la función get_mysql_metrics definida en mysql_monitor.py,
# la cual obtiene las métricas de MySQL y las devuelve como diccionario.
try:
    from mysql_monitor import get_mysql_metrics
except ImportError:
    sys.exit("No se encontró el módulo mysql_monitor. Asegúrate de tenerlo en tu PYTHONPATH.")

# Intentamos importar pymongo y, si no está instalado, lo instalamos automáticamente.
try:
    from pymongo import MongoClient
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pymongo"])
    from pymongo import MongoClient

def store_metrics_in_mongodb(metrics, mongo_uri=f"mongodb://{os.getenv('MONGO_USERNAME')}:{os.getenv('MONGO_PASSWORD')}@{os.getenv('MONGO_HOST')}:27017/", 
                               db_name="mysql_monitor", collection_name="metrics"):
    """
    Almacena el diccionario de métricas en MongoDB agregándole un timestamp.
    """
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]
    
    # Agregamos el timestamp de la medición (en UTC)
    metrics["timestamp"] = datetime.datetime.now(datetime.timezone.utc).timestamp()
    
    # Insertamos el documento en la colección
    result = collection.insert_one(metrics)
    print(f"Datos almacenados con _id: {result.inserted_id}")

def main():
    # Reemplaza estos parámetros según tu configuración de MySQL
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT')
    user = os.getenv('DB_USERNAME')
    password = os.getenv('DB_PASSWORD')
    
    # Obtener métricas desde MySQL
    metrics = get_mysql_metrics(host=host, port=port, user=user, password=password)
    
    # Almacenar en MongoDB
    store_metrics_in_mongodb(metrics)
    
    # También puedes imprimir en JSON para depuración o para redireccionar la salida
    print(json.dumps(metrics, indent=4, default=str))

if __name__ == "__main__":
    main()
