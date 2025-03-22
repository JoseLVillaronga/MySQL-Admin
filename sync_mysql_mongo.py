#!/usr/bin/env python3
import os
from dotenv import load_dotenv
import sys
import mysql.connector
from pymongo import MongoClient
from decimal import Decimal
from datetime import datetime, date, time, timezone, timedelta

# Cargar variables de entorno desde .env
load_dotenv()

def convert_data(data):
    """
    Recorre recursivamente el objeto 'data' y convierte:
      - Los Decimal a float.
      - Los objetos datetime.date (que no sean datetime) a datetime con zona UTC.
      - Los objetos timedelta a su valor en segundos.
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

def sync_database(mysql_config, mongo_client, database_name):
    """
    Sincroniza la base de datos MySQL a MongoDB:
      - Crea en MongoDB una base con el mismo nombre que la base MySQL.
      - Dentro de esa base, cada tabla (excluyendo vistas) se replica en una colección.
      - Se realiza una sincronización incremental basada en una columna de referencia:
          * Primero se busca una columna de tipo INT con auto_increment.
          * Si no se encuentra, se busca una columna de tipo datetime/timestamp con default CURRENT_TIMESTAMP.
      - Se actualiza el estado de sincronización en la base "sync_status", colección "sync_status",
        guardando "database", "table", "last_value" y "reference".
    """
    try:
        mysql_conn = mysql.connector.connect(database=database_name, **mysql_config)
    except mysql.connector.Error as err:
        sys.exit(f"Error al conectar a la base de datos {database_name}: {err}")
    
    cursor = mysql_conn.cursor(dictionary=True)
    
    # Obtener las tablas de la base de datos (excluyendo vistas)
    query_tables = """
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
    """
    cursor.execute(query_tables, (database_name,))
    tables = [row['TABLE_NAME'] for row in cursor.fetchall()]
    
    # Conectar a la colección de estado de sincronización
    sync_db = mongo_client["sync_status"]
    sync_status_collection = sync_db["sync_status"]
    
    for table in tables:
        print(f"Sincronizando tabla: {database_name}.{table}")
        
        # Analizar la estructura de la tabla para identificar el campo de referencia
        cursor.execute(f"DESCRIBE `{table}`")
        columns = cursor.fetchall()
        
        reference_column = None
        
        # Buscar columna de tipo INT con auto_increment
        for col in columns:
            extra = col.get("Extra", "").lower()
            col_type = col.get("Type", "")
            if isinstance(col_type, bytes):
                col_type = col_type.decode("utf-8")
            col_type = col_type.lower()
            if "auto_increment" in extra and "int" in col_type:
                reference_column = col["Field"]
                break
        
        # Si no se encontró, buscar columna de tipo datetime/timestamp con default CURRENT_TIMESTAMP
        if not reference_column:
            for col in columns:
                col_type = col.get("Type", "")
                if isinstance(col_type, bytes):
                    col_type = col_type.decode("utf-8")
                col_type = col_type.lower()
                default_val = col.get("Default", "")
                if isinstance(default_val, bytes):
                    default_val = default_val.decode("utf-8")
                if ("datetime" in col_type or "timestamp" in col_type) and default_val and "current_timestamp" in default_val.lower():
                    reference_column = col["Field"]
                    break
        
        if reference_column:
            print(f"Usando el campo de referencia '{reference_column}' para la tabla {table}")
        else:
            print(f"No se encontró campo de referencia para la tabla {table}. Se realizará una carga completa.")
        
        # Consultar el estado previo de sincronización para esta tabla
        status_doc = sync_status_collection.find_one({"database": database_name, "table": table})
        last_synced_value = status_doc.get("last_value") if status_doc else None
        
        # Preparar consulta incremental si hay referencia y estado previo
        if reference_column and last_synced_value is not None:
            # Verificamos si es un campo int o datetime/timestamp
            if "int" in col_type:
                # Para campos int, la comparación es directa
                query_data = f"SELECT * FROM `{table}` WHERE `{reference_column}` > %s"
                cursor.execute(query_data, (last_synced_value,))
            else:
                # Asumimos que es datetime/timestamp, así que convertimos con FROM_UNIXTIME
                query_data = f"SELECT * FROM `{table}` WHERE `{reference_column}` > FROM_UNIXTIME(%s)"
                cursor.execute(query_data, (last_synced_value,))
        else:
            # Si no hay referencia o no se encontró last_synced_value, se hace carga completa
            query_data = f"SELECT * FROM `{table}`"
            cursor.execute(query_data)
        
        rows = cursor.fetchall()
        if rows:
            # Convertir registros para que sean compatibles con BSON
            rows_converted = [convert_data(row) for row in rows]
            
            # Insertar registros en la colección de MongoDB correspondiente
            mongo_db = mongo_client[database_name]
            collection = mongo_db[table]
            try:
                collection.insert_many(rows_converted)
                print(f"Insertados {len(rows)} registros en {database_name}.{table}")
            except Exception as e:
                print(f"Error al insertar registros en {database_name}.{table}: {e}")
            
            # Actualizar el estado de sincronización si se usa un campo de referencia
            if reference_column:
                try:
                    if "int" in col_type:
                        # Campo int
                        max_val = max(int(r[reference_column]) for r in rows if r[reference_column] is not None)
                    else:
                        # Campo datetime/timestamp: obtener el valor máximo como float
                        max_val = max(r[reference_column].timestamp()  
                                    for r in rows
                                    if r[reference_column] is not None and isinstance(r[reference_column], datetime))

                    sync_status_collection.update_one(
                        {"database": database_name, "table": table},
                        {"$set": {"last_value": max_val, "reference": reference_column}},
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
    
    # Lista de bases de datos a sincronizar, separadas por comas
    databases = os.getenv("MYSQL_DATABASES", "").split(",")
    databases = [db.strip() for db in databases if db.strip()]
    
    if not databases:
        sys.exit("No se especificaron bases de datos en la variable MYSQL_DATABASES.")
    
    # Configuración de MongoDB desde variables de entorno
    mongo_uri = f"mongodb://{os.getenv('MONGO_USERNAME')}:{os.getenv('MONGO_PASSWORD')}@{os.getenv('MONGO_HOST')}:27017/"
    mongo_client = MongoClient(mongo_uri)
    
    # Sincronizar cada base de datos
    for db in databases:
        sync_database(mysql_config, mongo_client, db)

if __name__ == "__main__":
    main()
