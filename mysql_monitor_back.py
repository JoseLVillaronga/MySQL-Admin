#!/usr/bin/env python3
import sys
try:
    import mysql.connector
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mysql-connector-python"])
    import mysql.connector

import json
import argparse

def get_mysql_metrics(host="localhost", port=3306, user=None, password=None, database=None):
    """
    Conecta a MySQL y obtiene métricas mediante SHOW GLOBAL STATUS,
    devolviendo un diccionario con métricas seleccionadas.
    """
    conn_params = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
    }
    if database:
        conn_params["database"] = database

    try:
        conn = mysql.connector.connect(**conn_params)
    except mysql.connector.Error as err:
        sys.exit(f"Error al conectar a MySQL: {err}")
    
    cursor = conn.cursor()
    cursor.execute("SHOW GLOBAL STATUS")
    status = dict(cursor.fetchall())
    cursor.close()
    conn.close()

    # Selección de métricas relevantes
    metrics = {
        # Conexiones y threads
        "Connections": int(status.get("Connections", 0)),
        "Threads_connected": int(status.get("Threads_connected", 0)),
        "Threads_running": int(status.get("Threads_running", 0)),
        # Uptime
        "Uptime": int(status.get("Uptime", 0)),
        "Uptime_since_flush_status": int(status.get("Uptime_since_flush_status", 0)),
        # Actividad de consultas
        "Questions": int(status.get("Questions", 0)),
        "Slow_queries": int(status.get("Slow_queries", 0)),
        # Métricas InnoDB
        "Innodb_buffer_pool_read_requests": int(status.get("Innodb_buffer_pool_read_requests", 0)),
        "Innodb_buffer_pool_reads": int(status.get("Innodb_buffer_pool_reads", 0)),
        "Innodb_buffer_pool_pages_free": int(status.get("Innodb_buffer_pool_pages_free", 0)),
        "Innodb_buffer_pool_pages_total": int(status.get("Innodb_buffer_pool_pages_total", 0)),
        "Innodb_rows_inserted": int(status.get("Innodb_rows_inserted", 0)),
        "Innodb_rows_read": int(status.get("Innodb_rows_read", 0)),
        "Innodb_rows_updated": int(status.get("Innodb_rows_updated", 0)),
        "Innodb_rows_deleted": int(status.get("Innodb_rows_deleted", 0))
    }
    
    return metrics

def main():
    parser = argparse.ArgumentParser(
        description="Monitoriza MySQL y muestra métricas en formato JSON."
    )
    parser.add_argument("--host", type=str, default="localhost", help="Host de MySQL (default: localhost)")
    parser.add_argument("--port", type=int, default=3306, help="Puerto de MySQL (default: 3306)")
    parser.add_argument("--user", type=str, required=True, help="Usuario de MySQL")
    parser.add_argument("--password", type=str, required=True, help="Contraseña de MySQL")
    parser.add_argument("--database", type=str, default=None, help="Base de datos a conectar (opcional)")
    
    args = parser.parse_args()
    
    metrics = get_mysql_metrics(
        host=args.host, 
        port=args.port, 
        user=args.user, 
        password=args.password, 
        database=args.database
    )
    
    # Mostrar la salida en formato JSON
    print(json.dumps(metrics, indent=4))

if __name__ == "__main__":
    main()
