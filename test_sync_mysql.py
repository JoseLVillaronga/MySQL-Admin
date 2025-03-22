#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import sys
import mysql.connector
from pymongo import MongoClient
from decimal import Decimal
from datetime import datetime, date, time, timezone, timedelta

# Cargar variables de entorno
load_dotenv()

def convert_data(data):
    """
    Recorre recursivamente el objeto 'data' y convierte:
      - Los Decimal a float.
      - Los objetos datetime.date (que no sean datetime.datetime) a datetime.datetime con zona UTC.
      - Los objetos datetime.timedelta a su valor en segundos (total_seconds).
    """
    if isinstance(data, dict):
        return {k: convert_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_data(item) for item in data]
    elif isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, date) and not isinstance(data, datetime):
        return datetime.combine(data, time.min, tzinfo=timezone.utc)
    elif isinstance(data, timedelta):
        return data.total_seconds()
    else:
        return data

def convert_decimals(data):
    """
    Recorre el objeto 'data' y convierte los valores de tipo Decimal a float.
    """
    if isinstance(data, dict):
        return {k: convert_decimals(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_decimals(item) for item in data]
    elif isinstance(data, Decimal):
        return float(data)
    else:
        return data

def sync_database(mysql_config, mongo_client, database_name):
    """
    Realiza la sincronización de una base de datos MySQL a MongoDB:
      - Crea en MongoDB una base con el mismo nombre.
      - Dentro de esa base, crea una colección para cada tabla (excluye vistas).
      - Inserta todos los registros (o los nuevos, de forma incremental).
      - Usa una colección especial "sync_status" (en la base "sync_status")
        para guardar el último valor sincronizado de cada tabla.
    """
    # Conectar a la base de datos MySQL especificada
    try:
        mysql_conn = mysql.connector.connect(database=database_name, **mysql_config)
    except mysql.connector.Error as err:
        sys.exit(f"Error al conectar a la base de datos {database_name}: {err}")
    
    cursor = mysql_conn.cursor(dictionary=True)
    
    # Consultar las tablas (excluyendo vistas) usando INFORMATION_SCHEMA.TABLES
    query_tables = """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
    """
    cursor.execute(query_tables, (database_name,))
    tables = [row['TABLE_NAME'] for row in cursor.fetchall()]
    
    # Usaremos una base de datos en MongoDB para almacenar el estado de sincronización
    sync_db = mongo_client["sync_status"]
    sync_status_collection = sync_db["sync_status"]

    for table in tables:
        print(f"Sincronizando tabla: {database_name}.{table}")
        
        # Consultar el estado previo de sincronización para la tabla
        status_doc = sync_status_collection.find_one({"database": database_name, "table": table})
        last_synced_value = status_doc["last_value"] if status_doc else None

        # Identificar el campo incremental: por defecto se busca "id"
        # Si no existe, se intenta buscar alguna columna de fecha que contenga "created" en su nombre.
        cursor.execute(f"DESCRIBE `{table}`")
        columns = cursor.fetchall()
        incremental_column = None
        for col in columns:
            if col["Field"].lower() == "id":
                incremental_column = "id"
                break
        if not incremental_column:
            for col in columns:
                if "created" in col["Field"].lower():
                    incremental_column = col["Field"]
                    break

        # Preparar la consulta para obtener los registros nuevos.
        # Si existe un estado previo y se identificó un campo incremental,
        # se recuperan solo los registros donde el valor es mayor que el último sincronizado.
        if last_synced_value is not None and incremental_column:
            query_data = f"SELECT * FROM `{table}` WHERE `{incremental_column}` > %s"
            cursor.execute(query_data, (last_synced_value,))
        else:
            query_data = f"SELECT * FROM `{table}`"
            cursor.execute(query_data)
        
        rows = cursor.fetchall()
        if rows:
            # Convertir los valores Decimal en cada registro
            rows_converted = [convert_data(row) for row in rows]

            # Insertar los registros en la base MongoDB correspondiente
            mongo_db = mongo_client[database_name]
            collection = mongo_db[table]
            collection.insert_many(rows_converted)
            print(f"Insertados {len(rows)} registros en {database_name}.{table}")
            
            # Actualizar el último valor sincronizado si se usa un campo incremental
            if incremental_column:
                try:
                    # Asumimos que los valores son comparables (numéricos o fechas)
                    max_val = max(row[incremental_column] for row in rows)
                    sync_status_collection.update_one(
                        {"database": database_name, "table": table},
                        {"$set": {"last_value": max_val}},
                        upsert=True
                    )
                except Exception as e:
                    print(f"Advertencia al actualizar sync_status para {database_name}.{table}: {e}")
        else:
            print(f"No se encontraron registros nuevos en {database_name}.{table}")
    
    cursor.close()
    mysql_conn.close()

def main():
    # Configuración MySQL extraída de variables de entorno
    mysql_config = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "user": os.getenv("DB_USERNAME"),
        "password": os.getenv("DB_PASSWORD")
    }

    # Lista de bases de datos MySQL a sincronizar (por ejemplo, "db1,db2,db3")
    databases = os.getenv("MYSQL_DATABASES", "").split(",")
    databases = [db.strip() for db in databases if db.strip()]

    if not databases:
        sys.exit("No se especificaron bases de datos en la variable MYSQL_DATABASES.")

    # Configuración de MongoDB usando las variables de entorno
    mongo_uri = f"mongodb://{os.getenv('MONGO_USERNAME')}:{os.getenv('MONGO_PASSWORD')}@{os.getenv('MONGO_HOST')}:27017/"
    mongo_client = MongoClient(mongo_uri)

    # Para cada base de datos MySQL, se realiza la sincronización
    for db in databases:
        sync_database(mysql_config, mongo_client, db)

if __name__ == "__main__":
    main()
