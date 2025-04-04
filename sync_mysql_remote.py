import os
import sys
import logging
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import pymongo
from pymongo import MongoClient
import json

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync_mysql.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabaseConfig:
    def __init__(self, prefix: str):
        self.host = os.getenv(f"{prefix}_HOST")
        self.port = int(os.getenv(f"{prefix}_PORT", "3306"))
        self.username = os.getenv(f"{prefix}_USERNAME")
        self.password = os.getenv(f"{prefix}_PASSWORD")
        self.validate()

    def validate(self):
        if not all([self.host, self.username, self.password]):
            raise ValueError(f"Faltan parámetros de conexión para {self.__class__.__name__}")

class MongoLogger:
    def __init__(self):
        self.client = MongoClient(
            host=os.getenv("MONGO_HOST", "localhost"),
            username=os.getenv("MONGO_USERNAME"),
            password=os.getenv("MONGO_PASSWORD")
        )
        self.db = self.client.sync_logs
        self.collection = self.db.sync_history

    def log_sync_result(self, database: str, stats: Dict[str, Any]):
        log_entry = {
            "timestamp": datetime.now(),
            "database": database,
            "stats": stats,
            "status": "success" if stats["errors"] == 0 else "partial"
        }
        self.collection.insert_one(log_entry)

    def get_last_sync(self, database: str) -> Optional[datetime]:
        last_entry = self.collection.find_one(
            {"database": database},
            sort=[("timestamp", -1)]
        )
        return last_entry["timestamp"] if last_entry else None

class MySQLConnection:
    def __init__(self, config: DatabaseConfig, database: Optional[str] = None):
        self.config = config
        self.database = database
        self.connection = None
        self.cursor = None

    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.username,
                password=self.config.password,
                database=self.database
            )
            self.cursor = self.connection.cursor(dictionary=True)
            logger.info(f"Conexión exitosa a {self.config.host}")
            return True
        except Error as e:
            logger.error(f"Error conectando a MySQL en {self.config.host}: {e}")
            raise

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            logger.info("Conexión cerrada")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class TableAnalyzer:
    def __init__(self, connection: MySQLConnection):
        self.connection = connection

    def get_tables(self) -> List[str]:
        """Obtiene lista de tablas excluyendo vistas"""
        self.connection.cursor.execute("SHOW FULL TABLES")
        tables = [row[list(row.keys())[0]] for row in self.connection.cursor.fetchall() 
                 if row[list(row.keys())[1]] == "BASE TABLE"]
        return tables

    def get_table_columns(self, table: str) -> List[Dict[str, Any]]:
        """Obtiene información de columnas de una tabla"""
        self.connection.cursor.execute(f"SHOW COLUMNS FROM {table}")
        return self.connection.cursor.fetchall()

    def find_reference_field(self, columns: List[Dict[str, Any]]) -> Optional[str]:
        """Busca campo de referencia (autoincrement o datetime con NOW)"""
        for col in columns:
            col_type = col.get('Type', '')
            if isinstance(col_type, bytes):
                col_type = col_type.decode('utf-8')
            col_type = col_type.lower()
            
            # Buscar campo autoincrement
            if col.get('Extra') == 'auto_increment' and 'int' in col_type:
                return col['Field']
            
            # Buscar campo datetime o timestamp con DEFAULT CURRENT_TIMESTAMP
            default_val = col.get('Default', '')
            if isinstance(default_val, bytes):
                default_val = default_val.decode('utf-8')
            
            if ('datetime' in col_type or 'timestamp' in col_type) and default_val and 'current_timestamp' in str(default_val).lower():
                return col['Field']
        
        return None

    def get_foreign_keys(self, table: str) -> List[str]:
        """Obtiene lista de claves foráneas de una tabla"""
        self.connection.cursor.execute(f"""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = '{table}'
            AND REFERENCED_TABLE_NAME IS NOT NULL
        """)
        return [row['COLUMN_NAME'] for row in self.connection.cursor.fetchall()]

    def analyze_tables(self) -> List[Dict[str, Any]]:
        """Analiza todas las tablas y retorna información estructurada"""
        tables_info = []
        tables = self.get_tables()
        
        for table in tables:
            columns = self.get_table_columns(table)
            reference_field = self.find_reference_field(columns)
            foreign_keys = self.get_foreign_keys(table)
            
            if reference_field:  # Solo incluir tablas con campo de referencia válido
                tables_info.append({
                    'name': table,
                    'reference_field': reference_field,
                    'foreign_keys': foreign_keys,
                    'has_foreign_keys': len(foreign_keys) > 0
                })
        
        # Ordenar tablas: primero las que no tienen claves foráneas
        return sorted(tables_info, key=lambda x: x['has_foreign_keys'])

class TableSync:
    def __init__(self, remote_conn: MySQLConnection, local_conn: MySQLConnection, 
                 table_info: Dict[str, Any], mongo_logger: MongoLogger):
        self.remote_conn = remote_conn
        self.local_conn = local_conn
        self.table = table_info['name']
        self.reference_field = table_info['reference_field']
        self.mongo_logger = mongo_logger
        self.stats = {
            'rows_processed': 0,
            'rows_inserted': 0,
            'errors': 0
        }

    def get_max_local_value(self) -> Any:
        """Obtiene el valor máximo del campo de referencia en la tabla local"""
        self.local_conn.cursor.execute(f"SELECT MAX({self.reference_field}) as max_value FROM {self.table}")
        result = self.local_conn.cursor.fetchone()
        return result['max_value'] if result and result['max_value'] is not None else None

    def sync_table(self):
        """Sincroniza una tabla específica"""
        logger.info(f"Iniciando sincronización de tabla: {self.table}")
        
        try:
            max_local_value = self.get_max_local_value()
            
            # Obtener registros nuevos de la tabla remota
            if max_local_value is not None:
                query = f"SELECT * FROM {self.table} WHERE {self.reference_field} > %s"
                self.remote_conn.cursor.execute(query, (max_local_value,))
            else:
                self.remote_conn.cursor.execute(f"SELECT * FROM {self.table}")
            
            new_rows = self.remote_conn.cursor.fetchall()
            
            if new_rows:
                # Preparar inserción de registros nuevos
                columns = list(new_rows[0].keys())
                placeholders = ", ".join(["%s"] * len(columns))
                insert_query = f"INSERT INTO {self.table} ({', '.join(columns)}) VALUES ({placeholders})"
                
                # Insertar registros
                for row in new_rows:
                    try:
                        data = [row[col] for col in columns]
                        self.local_conn.cursor.execute(insert_query, data)
                        self.stats['rows_inserted'] += 1
                    except Error as e:
                        logger.error(f"Error insertando fila en {self.table}: {e}")
                        self.stats['errors'] += 1
                    finally:
                        self.stats['rows_processed'] += 1
                
                self.local_conn.connection.commit()
                logger.info(f"Tabla {self.table} sincronizada: {self.stats['rows_inserted']} filas insertadas")
            
        except Error as e:
            logger.error(f"Error sincronizando tabla {self.table}: {e}")
            raise

class ChangelogSynchronizer:
    def __init__(self, database: str):
        self.database = database
        # Conectar al MongoDB remoto que contiene el changelog
        self.client = MongoClient(
            host=os.getenv("MONGOR_HOST", "localhost"),
            username=os.getenv("MONGOR_USERNAME"),
            password=os.getenv("MONGOR_PASSWORD")
        )
        self.db = self.client.teccam_mongo
        self.changelog = self.db.changelog
        self.stats = {
            'updates_processed': 0,
            'updates_applied': 0,
            'errors': 0
        }
        
    def get_recent_changes(self, minutes: int = 2) -> List[Dict[str, Any]]:
        """Obtiene cambios recientes del changelog (últimos X minutos)"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        # Convertir a string de fecha para comparación
        cutoff_str = cutoff_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Filtrar por base de datos y tiempo
        query = {
            "base_datos": self.database,
            "fecha_operacion": {"$gte": cutoff_str}
        }
        
        # Ordenar por fecha ascendente para procesar en orden cronológico
        changes = list(self.changelog.find(query).sort("fecha_operacion", 1))
        
        logger.info(f"Encontrados {len(changes)} cambios recientes en {self.database}")
        return changes
    
    def apply_changes_to_local(self, changes: List[Dict[str, Any]], local_conn: MySQLConnection):
        """Aplica los cambios del changelog a la base de datos local"""
        for change in changes:
            try:
                operation = change.get("operacion")
                table = change.get("tabla")
                record_id = change.get("id_registro")
                
                if not all([operation, table, record_id]):
                    logger.warning(f"Registro de cambio incompleto: {change}")
                    continue
                
                self.stats['updates_processed'] += 1
                
                if operation == "UPDATE" and "estado_actual" in change:
                    self._apply_update(local_conn, table, record_id, change["estado_actual"])
                    
                # También podríamos manejar DELETE en el futuro si es necesario
                
            except Exception as e:
                logger.error(f"Error al aplicar cambio {change.get('_id')}: {e}")
                self.stats['errors'] += 1
    
    def _apply_update(self, conn: MySQLConnection, table: str, record_id: Any, current_state: Dict[str, Any]):
        """Aplica una actualización a un registro existente"""
        try:
            # Obtener todas las columnas del estado actual
            columns = []
            values = []
            
            # Filtramos los campos que no son parte de la tabla (como _id de MongoDB)
            for key, value in current_state.items():
                if not key.startswith('_'):
                    columns.append(key)
                    values.append(value)
            
            if not columns:
                logger.warning(f"No hay columnas para actualizar en la tabla {table}, registro {record_id}")
                return
            
            # Construir query de actualización
            set_clause = ", ".join([f"`{col}`=%s" for col in columns])
            
            # Identificar columna ID basada en el patrón común (tabla_id)
            id_column = None
            for col in columns:
                if col.endswith('_id') and current_state.get(col) == record_id:
                    id_column = col
                    break
            
            if not id_column:
                # Si no hay patrón claro, asumimos que la tabla tiene una columna primary key estándar
                id_column = f"{table}_id"
            
            query = f"UPDATE `{table}` SET {set_clause} WHERE `{id_column}` = %s"
            
            # Agregar el valor del ID al final para el WHERE
            values.append(record_id)
            
            # Ejecutar la actualización
            conn.cursor.execute(query, values)
            conn.connection.commit()
            
            self.stats['updates_applied'] += 1
            logger.info(f"Actualizado registro {record_id} en tabla {table}")
            
        except Error as e:
            logger.error(f"Error actualizando registro {record_id} en tabla {table}: {e}")
            self.stats['errors'] += 1
            # No hacemos rollback, continuamos con los siguientes cambios

class DatabaseSync:
    def __init__(self, database: str):
        self.database = database
        self.remote_config = DatabaseConfig("DBR")
        self.local_config = DatabaseConfig("DB")
        self.mongo_logger = MongoLogger()
        self.sync_stats = {
            'tables_processed': 0,
            'tables_success': 0,
            'tables_failed': 0,
            'total_rows_processed': 0,
            'total_rows_inserted': 0,
            'total_updates_processed': 0,
            'total_updates_applied': 0,
            'errors': 0
        }

    def sync_database(self):
        """Sincroniza una base de datos completa"""
        logger.info(f"Iniciando sincronización de base de datos: {self.database}")
        
        try:
            # Primero analizar estructura usando la base local
            with MySQLConnection(self.local_config, self.database) as local_conn:
                analyzer = TableAnalyzer(local_conn)
                tables_info = analyzer.analyze_tables()
            
            # Procesar cada tabla en orden
            with MySQLConnection(self.remote_config, self.database) as remote_conn, \
                 MySQLConnection(self.local_config, self.database) as local_conn:
                
                # Primero sincronizar inserciones nuevas
                for table_info in tables_info:
                    try:
                        table_sync = TableSync(remote_conn, local_conn, table_info, self.mongo_logger)
                        table_sync.sync_table()
                        
                        # Actualizar estadísticas
                        self.sync_stats['tables_success'] += 1
                        self.sync_stats['total_rows_processed'] += table_sync.stats['rows_processed']
                        self.sync_stats['total_rows_inserted'] += table_sync.stats['rows_inserted']
                        self.sync_stats['errors'] += table_sync.stats['errors']
                    except Error as e:
                        logger.error(f"Error en tabla {table_info['name']}: {e}")
                        self.sync_stats['tables_failed'] += 1
                    finally:
                        self.sync_stats['tables_processed'] += 1
                        
                # Ahora procesar actualizaciones desde el changelog de MongoDB
                try:
                    changelog_sync = ChangelogSynchronizer(self.database)
                    recent_changes = changelog_sync.get_recent_changes()
                    
                    if recent_changes:
                        changelog_sync.apply_changes_to_local(recent_changes, local_conn)
                        
                        # Actualizar estadísticas
                        self.sync_stats['total_updates_processed'] += changelog_sync.stats['updates_processed']
                        self.sync_stats['total_updates_applied'] += changelog_sync.stats['updates_applied']
                        self.sync_stats['errors'] += changelog_sync.stats['errors']
                        
                        logger.info(f"Aplicados {changelog_sync.stats['updates_applied']} cambios de {changelog_sync.stats['updates_processed']} del changelog")
                except Exception as e:
                    logger.error(f"Error procesando changelog para {self.database}: {e}")
                    self.sync_stats['errors'] += 1

                # Registrar resultados en MongoDB
                self.mongo_logger.log_sync_result(self.database, self.sync_stats)
                self._generate_report()
                
        except Error as e:
            logger.error(f"Error sincronizando base de datos {self.database}: {e}")
            raise

    def _generate_report(self):
        """Genera reporte de sincronización"""
        report = f"""
        Reporte de Sincronización - {self.database}
        ======================================
        Tablas procesadas: {self.sync_stats['tables_processed']}
        Tablas exitosas: {self.sync_stats['tables_success']}
        Tablas fallidas: {self.sync_stats['tables_failed']}
        Total de filas procesadas: {self.sync_stats['total_rows_processed']}
        Total de filas insertadas: {self.sync_stats['total_rows_inserted']}
        Total de cambios procesados: {self.sync_stats['total_updates_processed']}
        Total de cambios aplicados: {self.sync_stats['total_updates_applied']}
        Errores encontrados: {self.sync_stats['errors']}
        """
        logger.info(report)

def main():
    load_dotenv()
    
    try:
        databases = os.getenv("MYSQL_DATABASES")
        if not databases:
            logger.error("No se han configurado bases de datos en MYSQL_DATABASES en el .env")
            sys.exit(1)

        databases_list = [db.strip() for db in databases.split(",") if db.strip()]
        for db in databases_list:
            try:
                sync = DatabaseSync(db)
                sync.sync_database()
            except Exception as e:
                logger.error(f"Error procesando base de datos {db}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error general: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
