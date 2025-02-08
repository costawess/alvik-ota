import dash
from dash import dcc, html
import plotly.graph_objs as go
from dash.dependencies import Input, Output
import paho.mqtt.client as mqtt
import json
import threading
import time
import pandas as pd

baseline = 400  # Sensibilidade extra para ajustes finos

# ------------------- CONFIGURAÇÃO MQTT -------------------
MQTT_BROKER = "192.168.2.14"  # IP do Broker MQTT
MQTT_TOPIC = "alvik/sensors"

# Data storage
data = {"timestamp": [], "left": [], "center": [], "right": []}
sensor_alerts = []  # Stores which sensors are above 500

# Função chamada quando uma mensagem MQTT é recebida
def on_message(client, _, msg):
    global data, sensor_alerts
    try:
        payload = json.loads(msg.payload.decode())
        timestamp = payload.get("timestamp", time.time())
        left = payload.get("left", 0)
        center = payload.get("center", 0)
        right = payload.get("right", 0)

        # Adicionar os dados na estrutura
        data["timestamp"].append(timestamp)
        data["left"].append(left)
        data["center"].append(center)
        data["right"].append(right)

        # Atualizar lista de sensores acima de 500
        active_sensors = []
        if left > baseline:
            active_sensors.append("Left")
        if center > baseline:
            active_sensors.append("Center")
        if right > baseline:
            active_sensors.append("Right")
        sensor_alerts[:] = active_sensors  # Update global variable

        # Manter os últimos 100 registros para não sobrecarregar
        if len(data["timestamp"]) > 100:
            for key in data.keys():
                data[key] = data[key][-100:]

    except Exception as e:
        print(f"Erro ao processar mensagem MQTT: {e}")

# Conectar ao Broker MQTT em uma thread separada
def connect_mqtt():
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()  # Rodar em segundo plano

# Iniciar MQTT em uma thread separada
threading.Thread(target=connect_mqtt, daemon=True).start()

# ------------------- DASHBOARD DASH -------------------
app = dash.Dash(__name__, assets_folder='assets')

app.layout = html.Div([
    html.H1("Dashboard do Alvik - Sensores"),
    
    html.Div([
        # Left Side: Live Graph
        html.Div([
            dcc.Graph(id="live-graph"),
        ], className="six columns"),
        
        # Right Side: Active Sensors Above 500
        html.Div([
            html.H3(f"Sensores Ativados (>{baseline}):"),
            html.Ul(id="sensor-status", style={"fontSize": "20px", "color": "red"})
        ], className="six columns"),
    ], className="row"),
    
    dcc.Interval(
        id="interval-component",
        interval=1000,  # Atualiza a cada 1 segundo
        n_intervals=0
    )
])

@app.callback(
    Output("live-graph", "figure"),
    Input("interval-component", "n_intervals")
)
def update_graph(_):
    global data
    if not data["timestamp"]:
        return go.Figure()

    df = pd.DataFrame(data)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["left"], mode="lines", name="Sensor Left"))
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["center"], mode="lines", name="Sensor Center"))
    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["right"], mode="lines", name="Sensor Right"))

    fig.update_layout(
        title="Leitura dos Sensores ao Longo do Tempo",
        xaxis_title="Tempo",
        yaxis_title="Valor do Sensor",
        legend_title="Sensores",
        template="plotly_dark",
        plot_bgcolor="black",
        paper_bgcolor="black"
    )
    
    return fig

@app.callback(
    Output("sensor-status", "children"),
    Input("interval-component", "n_intervals")
)
def update_sensor_status(_):
    if not sensor_alerts:
        return [html.Li("Nenhum sensor acima de 500", style={"color": "green"})]
    return [html.Li(f"{sensor}", style={"color": "red"}) for sensor in sensor_alerts]

if __name__ == "__main__":
    app.run_server(debug=True, port=8080)
