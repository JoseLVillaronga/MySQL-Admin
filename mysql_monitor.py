#!/usr/bin/env python3
import sys
import json
import argparse

# Intentamos importar mysql-connector-python, sino lo instalamos automáticamente
try:
    import mysql.connector
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "mysql-connector-python"])
    import mysql.connector

# Intentamos importar psutil, sino lo instalamos automáticamente
try:
    import psutil
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
    import psutil

def get_system_metrics(process_name="mysqld"):
    """
    Obtiene el uso de CPU y la memoria (en bytes) consumida por el proceso MySQL.
    Busca todos los procesos cuyo nombre contenga 'mysqld' (no distingue mayúsculas/minúsculas)
    y suma sus valores.
    """
    total_cpu = 0.0
    total_memory = 0
    for proc in psutil.process_iter(attrs=["name", "cpu_percent", "memory_info"]):
        try:
            nombre = proc.info.get("name", "")
            if process_name.lower() in nombre.lower():
                # Se usa un intervalo corto para obtener un valor actualizado de CPU
                cpu = proc.cpu_percent(interval=0.1)
                total_cpu += cpu
                total_memory += proc.memory_info().rss  # Memoria en bytes (RSS)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return total_cpu, total_memory

def get_mysql_metrics(host="localhost", port=3306, user=None, password=None, database=None):
    """
    Conecta a MySQL y obtiene métricas mediante SHOW GLOBAL STATUS,
    devolviendo un diccionario con métricas seleccionadas y las métricas
    del sistema (uso de CPU y memoria) del proceso MySQL.
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

    # Métricas seleccionadas de MySQL
    metrics = {
        "Connections": int(status.get("Connections", 0)),
        "Threads_connected": int(status.get("Threads_connected", 0)),
        "Threads_running": int(status.get("Threads_running", 0)),
        "Uptime": int(status.get("Uptime", 0)),
        "Uptime_since_flush_status": int(status.get("Uptime_since_flush_status", 0)),
        "Questions": int(status.get("Questions", 0)),
        "Slow_queries": int(status.get("Slow_queries", 0)),
        "Innodb_buffer_pool_read_requests": int(status.get("Innodb_buffer_pool_read_requests", 0)),
        "Innodb_buffer_pool_reads": int(status.get("Innodb_buffer_pool_reads", 0)),
        "Innodb_buffer_pool_pages_free": int(status.get("Innodb_buffer_pool_pages_free", 0)),
        "Innodb_buffer_pool_pages_total": int(status.get("Innodb_buffer_pool_pages_total", 0)),
        "Innodb_rows_inserted": int(status.get("Innodb_rows_inserted", 0)),
        "Innodb_rows_read": int(status.get("Innodb_rows_read", 0)),
        "Innodb_rows_updated": int(status.get("Innodb_rows_updated", 0)),
        "Innodb_rows_deleted": int(status.get("Innodb_rows_deleted", 0))
    }
    
    # Agregar métricas del sistema para el proceso MySQL
    cpu_usage, memory_used = get_system_metrics("mysqld")
    metrics["mysql_cpu_usage_percent"] = cpu_usage
    metrics["mysql_memory_used_bytes"] = memory_used
    
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
    
    print(json.dumps(metrics, indent=4))

if __name__ == "__main__":
    main()
