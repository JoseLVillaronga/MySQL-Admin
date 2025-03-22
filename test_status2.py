import mysql.connector
import time

def obtener_status():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="teccamsql365"
    )
    cursor = conn.cursor()
    cursor.execute("SHOW GLOBAL STATUS")
    status = dict(cursor.fetchall())
    cursor.close()
    conn.close()
    return status

# Medición inicial
status_inicial = obtener_status()
time.sleep(60)  # Espera 60 segundos para calcular la tasa
status_final = obtener_status()

# Ejemplo: calcular consultas por segundo
q_inicial = int(status_inicial.get("Questions", 0))
q_final = int(status_final.get("Questions", 0))
tasa_consultas = (q_final - q_inicial) / 60

print(f"Tasa de consultas por segundo: {tasa_consultas:.2f}")
