import os
import sys
import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


def get_db_connection():
    """
    Establece la conexión a la base de datos MongoDB utilizando las credenciales del entorno.
    """
    mongo_uri = f"mongodb://{os.getenv('MONGO_USERNAME')}:{os.getenv('MONGO_PASSWORD')}@{os.getenv('MONGO_HOST')}:27017/"
    try:
        client = MongoClient(mongo_uri)
        db = client['mysql_monitor']
        return db
    except Exception as e:
        sys.exit(f"Error al conectar a MongoDB: {e}")


def analyze_metrics(limit=10):
    """
    Recupera y muestra las métricas más recientes almacenadas en la colección 'metrics' de la base 'mysql_monitor'.
    
    Parámetros:
    - limit: Número máximo de documentos a recuperar (por defecto 10).
    """
    db = get_db_connection()
    collection = db['metrics']

    # Recuperar los documentos de métricas ordenados de forma descendente por timestamp
    try:
        docs = list(collection.find().sort("timestamp", -1).limit(limit))
    except Exception as e:
        sys.exit(f"Error al obtener métricas: {e}")

    if not docs:
        print("No se encontraron métricas en la base de datos.")
        return

    print(f"Mostrando las {len(docs)} métricas más recientes:\n")
    for doc in docs:
        ts = datetime.datetime.fromtimestamp(doc.get("timestamp", 0), datetime.timezone.utc)
        # Excluimos el _id para una salida más limpia
        metrics_info = { key: value for key, value in doc.items() if key != '_id' }
        print(f"Timestamp: {ts.isoformat()}\nMétricas: {metrics_info}\n{'-'*40}")


if __name__ == "__main__":
    # Se puede extender con argumentos de línea de comando para análisis más avanzados
    analyze_metrics()
