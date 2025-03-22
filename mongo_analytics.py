#!/usr/bin/env python3
import os
import sys
import json
from dotenv import load_dotenv
from pymongo import MongoClient

# Cargar variables de entorno
load_dotenv()

def generate_report(mongo_uri, exclude_db="sync_status"):
    """
    Conecta a MongoDB y genera un reporte con estadísticas básicas de cada base de datos
    (excepto la base de sincronización 'sync_status'). Para cada base de datos se listan las
    colecciones y se reporta, por ejemplo, la cantidad de documentos.
    """
    client = MongoClient(mongo_uri)
    report = {}

    # Obtener la lista de bases de datos
    databases = client.list_database_names()
    # Excluir la base usada para almacenar el estado de sincronización
    databases = [db for db in databases if db != exclude_db]

    for db_name in databases:
        db = client[db_name]
        collections = db.list_collection_names()
        db_report = {}
        for coll in collections:
            # Usamos estimated_document_count para obtener un conteo rápido
            count = db[coll].estimated_document_count()
            db_report[coll] = {
                "record_count": count
                # Aquí podrías agregar otros parámetros, por ejemplo,
                # última fecha de actualización si la incluyeras en los documentos,
                # tamaño de la colección, etc.
            }
        report[db_name] = db_report

    return report

def main():
    # Construir la URI de MongoDB a partir de las variables de entorno
    mongo_uri = f"mongodb://{os.getenv('MONGO_USERNAME')}:{os.getenv('MONGO_PASSWORD')}@{os.getenv('MONGO_HOST')}:27017/"
    
    report = generate_report(mongo_uri)
    # Imprimir el reporte en formato JSON para facilitar su lectura o procesamiento
    print(json.dumps(report, indent=4))

if __name__ == "__main__":
    main()
