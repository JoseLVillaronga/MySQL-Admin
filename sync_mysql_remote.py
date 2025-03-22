import os
import sys
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()


def get_mysql_connection(host, port, user, password, database=None):
    try:
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database if database else None
        )
        return conn
    except Error as e:
        print(f"Error connecting to MySQL on {host}:{port} - {e}")
        sys.exit(1)


def sync_database(database):
    print(f"\nSyncing database: {database}")

    # Remote connection parameters
    remote_host = os.getenv("DBR_HOST")
    remote_port = os.getenv("DBR_PORT")
    remote_user = os.getenv("DBR_USERNAME")
    remote_password = os.getenv("DBR_PASSWORD")

    # Local connection parameters
    local_host = os.getenv("DB_HOST")
    local_port = os.getenv("DB_PORT")
    local_user = os.getenv("DB_USERNAME")
    local_password = os.getenv("DB_PASSWORD")

    # Connect to remote and local MySQL servers for the given database
    remote_conn = get_mysql_connection(remote_host, remote_port, remote_user, remote_password, database)
    local_conn = get_mysql_connection(local_host, local_port, local_user, local_password, database)

    try:
        remote_cursor = remote_conn.cursor(dictionary=True)
        local_cursor = local_conn.cursor()

        # Fetch list of tables from the remote database
        remote_cursor.execute("SHOW FULL TABLES")
        tables = remote_cursor.fetchall()
        table_names = []
        for row in tables:
            key_list = list(row.keys())
            table_name = row[key_list[0]]
            table_type = row[key_list[1]] if len(key_list) > 1 else "BASE TABLE"
            if table_type == "BASE TABLE":
                table_names.append(table_name)

        for table in table_names:
            print(f"\nSyncing table: {table}")
            # Fetch all rows from remote table
            remote_cursor.execute(f"SELECT * FROM {table}")
            rows = remote_cursor.fetchall()

            # Fetch column information from remote table
            remote_cursor.execute(f"SHOW COLUMNS FROM {table}")
            columns = remote_cursor.fetchall()
            col_names = [col['Field'] for col in columns]
            cols = ", ".join(col_names)
            placeholders = ", ".join(["%s"] * len(col_names))

            # Disable foreign key checks and clear local table
            local_cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            local_cursor.execute(f"TRUNCATE TABLE {table}")
            local_conn.commit()

            if rows:
                insert_query = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
                data = [tuple(row[col] for col in col_names) for row in rows]
                local_cursor.executemany(insert_query, data)
                local_conn.commit()
                print(f"Inserted {local_cursor.rowcount} rows into {table}")
            else:
                print(f"No data found in table {table}")

        print(f"\nDatabase '{database}' synced successfully.")

    except Error as e:
        print(f"Error during synchronization of database '{database}': {e}")
    finally:
        if remote_cursor:
            remote_cursor.close()
        if local_cursor:
            local_cursor.close()
        if remote_conn:
            remote_conn.close()
        if local_conn:
            local_conn.close()


def main():
    # Get list of databases to sync from environment variable
    databases = os.getenv("MYSQL_DATABASES")
    if not databases:
        print("No se han configurado bases de datos en MYSQL_DATABASES en el .env")
        sys.exit(1)

    databases_list = [db.strip() for db in databases.split(",") if db.strip()]
    for db in databases_list:
        sync_database(db)


if __name__ == "__main__":
    main()
