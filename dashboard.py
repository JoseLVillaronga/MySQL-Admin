import os
import datetime
import pytz
from flask import Flask, request, render_template
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
    interval = request.args.get('interval', '1h')
    zona_horaria = pytz.timezone(os.getenv('TZ', 'UTC'))
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

    db = get_db_connection()
    collection = db['metrics']
    data = list(collection.find({"timestamp": {"$gte": start_ts}}).sort("timestamp", 1))

    if not data:
        return render_template('dashboard.html', interval=interval, graph_div=None)

    times = [datetime.datetime.fromtimestamp(doc['timestamp'], zona_horaria) for doc in data]
    cpu = [doc.get("mysql_cpu_usage_percent", 0) for doc in data]
    memory = [doc.get("mysql_memory_used_bytes", 0) for doc in data]
    questions = [doc.get("Questions", 0) for doc in data]
    transactions = [0]
    for i in range(1, len(questions)):
        transactions.append(questions[i] - questions[i - 1])

    trace_cpu = go.Scatter(x=times, y=cpu, mode='lines+markers', name='CPU (%)',
                           line=dict(color='#007bff', shape='spline', smoothing=1.3), marker=dict(size=6))
    trace_memory = go.Scatter(x=times, y=memory, mode='lines+markers', name='Memoria (Bytes)',
                              line=dict(color='#28a745', shape='spline', smoothing=1.3), marker=dict(size=6))
    trace_transactions = go.Scatter(x=times, y=transactions, mode='lines+markers', name='Transacciones',
                                    line=dict(color='#fd7e14', shape='spline', smoothing=1.3), marker=dict(size=6))

    layout = go.Layout(
        title=f'Métricas de MySQL - Intervalo {interval}',
        xaxis=dict(title='Tiempo', tickformat='%H:%M\n%d-%m'),
        yaxis=dict(title='Valores'),
        legend=dict(orientation="h", y=-0.2),
        hovermode='x unified',
        margin=dict(l=50, r=30, t=50, b=80),
        template='plotly_white',
    )

    fig = go.Figure(data=[trace_cpu, trace_memory, trace_transactions], layout=layout)
    graph_div = opy.plot(fig, auto_open=False, output_type='div')

    return render_template('dashboard.html', interval=interval, graph_div=graph_div)


if __name__ == '__main__':
    # Ejecutar la aplicación en modo debug y en el puerto 5000
    app.run(debug=True, host='0.0.0.0', port=5306)
