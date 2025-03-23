import os
import datetime
import pytz
from flask import Flask, request
from pymongo import MongoClient
import plotly.graph_objs as go
import plotly.offline as opy
from dotenv import load_dotenv

# Cargar variables de entorno
deprecated_load = load_dotenv()

app = Flask(__name__)


def get_db_connection():
    """Establece la conexión a la base de datos MongoDB usando las credenciales del entorno."""
    mongo_uri = f"mongodb://{os.getenv('MONGO_USERNAME')}:{os.getenv('MONGO_PASSWORD')}@{os.getenv('MONGO_HOST')}:27017/"
    client = MongoClient(mongo_uri)
    db = client['mysql_monitor']
    return db


@app.route('/')
def index():
    # Obtener el intervalo deseado a través de parámetros de URL; por defecto 1h
    interval = request.args.get('interval', '1h')
    zona_horaria = pytz.timezone(os.getenv('TZ'))
    now = datetime.datetime.now(zona_horaria)
    
    # Determinar el tiempo de inicio en función del intervalo
    if interval == '1h':
        start_time = now - datetime.timedelta(hours=1)
    elif interval == '6h':
        start_time = now - datetime.timedelta(hours=6)
    elif interval == '24h':
        start_time = now - datetime.timedelta(hours=24)
    elif interval == '30d':
        start_time = now - datetime.timedelta(days=30)
    else:
        start_time = now - datetime.timedelta(hours=1)

    start_ts = start_time.timestamp()
    
    # Conexión a la base de datos y recuperación de métricas
    db = get_db_connection()
    collection = db['metrics']
    data = list(collection.find({"timestamp": {"$gte": start_ts}}).sort("timestamp", 1))
    
    if not data:
        return f"No se encontraron métricas para el intervalo {interval}" 

    # Extraer datos
    times = [datetime.datetime.fromtimestamp(doc['timestamp'], zona_horaria) for doc in data]
    cpu = [doc.get("mysql_cpu_usage_percent", 0) for doc in data]
    memory = [doc.get("mysql_memory_used_bytes", 0) for doc in data]
    # Utilizar el campo 'Questions' para calcular las transacciones
    questions = [doc.get("Questions", 0) for doc in data]

    # Calcular transacciones por intervalo (diferencia entre registros consecutivos)
    transactions = [0]  # primer registro no tiene comparación
    for i in range(1, len(questions)):
        transactions.append(questions[i] - questions[i - 1])

    # Crear trazas para cada métrica
    trace_cpu = go.Scatter(x=times, y=cpu, mode='lines+markers', name='CPU Usage (%)')
    trace_memory = go.Scatter(x=times, y=memory, mode='lines+markers', name='Memory Used (Bytes)')
    trace_transactions = go.Scatter(x=times, y=transactions, mode='lines+markers', name='Transactions per Interval')

    layout = go.Layout(
        title=f'Métricas de MySQL - Intervalo {interval}',
        xaxis=dict(title='Tiempo'),
        yaxis=dict(title='Valores'),
        hovermode='closest'
    )

    fig = go.Figure(data=[trace_cpu, trace_memory, trace_transactions], layout=layout)
    graph_div = opy.plot(fig, auto_open=False, output_type='div')

    # HTML simple con instrucciones y el gráfico interactivo
    html = f"""
    <html>
        <head>
            <title>Dashboard MySQL Monitor</title>
            <meta name='viewport' content='width=device-width, initial-scale=1'>
        </head>
        <body>
            <h1>Dashboard MySQL Monitor</h1>
            <p>Intervalo de datos: {interval}</p>
            {graph_div}
            <p>Usa el parámetro <code>interval</code> en la URL para cambiar el rango de datos. Ejemplos:</p>
            <ul>
                <li><a href='/?interval=1h'>Última hora</a></li>
                <li><a href='/?interval=6h'>Últimas 6 horas</a></li>
                <li><a href='/?interval=24h'>Último día</a></li>
                <li><a href='/?interval=30d'>Último mes</a></li>
            </ul>
        </body>
    </html>
    """
    return html


if __name__ == '__main__':
    # Ejecutar la aplicación en modo debug y en el puerto 5000
    app.run(debug=True, host='0.0.0.0', port=5306)
