import mysql.connector

# Conexión a la base de datos MySQL
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="teccamsql365",
    database="cdr"  # Opcional si solo usas SHOW GLOBAL STATUS
)

cursor = conn.cursor()

# Ejemplo: obtener variables de estado global
cursor.execute("SHOW GLOBAL STATUS")
for variable, valor in cursor.fetchall():
    print(f"{variable}: {valor}")

cursor.close()
conn.close()
