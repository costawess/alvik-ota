import dash
from dash import dcc, html
import plotly.graph_objs as go
from dash.dependencies import Input, Output
import paho.mqtt.client as mqtt
import json
import threading
import time
import pandas as pd

baseline = 500  # Sensibilidade para ativação dos sensores

# ------------------- CONFIGURAÇÃO MQTT -------------------
MQTT_BROKER = "192.168.2.14"  # IP do Broker MQTT
MQTT_TOPIC = "alvik/sensors"

# Data storage
data = {
    "timestamp": [],
    "left": [],
    "center": [],
    "right": [],
    "accel_x": [],
    "accel_y": [],
    "accel_z": [],
    "gyro_x": [],
    "gyro_y": [],
    "gyro_z": [],
    "pose_x": [],
    "pose_y": [],
    "pose_theta": [],
    "speed_left": [],
    "speed_right": [],
}
sensor_alerts = []  # Stores which sensors are above baseline

# MQTT Callback Function
# MQTT Callback Function
def on_message(client, _, msg):
    global data, sensor_alerts
    try:
        payload_raw = msg.payload.decode()
        print(f"📥 RAW MQTT MESSAGE: {payload_raw}")  # Debugging incoming data

        payload = json.loads(payload_raw)  # Decode JSON
        timestamp = payload.get("timestamp", time.time())

        # Store new data points
        for key in data.keys():
            if key in payload:
                if isinstance(payload[key], list) and len(payload[key]) == 2:  # Handle "speed" list correctly
                    data["speed_left"].append(payload[key][0])
                    data["speed_right"].append(payload[key][1])
                else:
                    data[key].append(payload[key])

        # Keep only the last 100 records to avoid overload
        for key in data.keys():
            data[key] = data[key][-100:]

        # Identify active sensors above the baseline
        active_sensors = [key for key in ["left", "center", "right"] if payload.get(key, 0) > baseline]
        sensor_alerts[:] = active_sensors  # Update global variable

    except json.JSONDecodeError as e:
        print(f"❌ JSON Decode Error: {e} - Raw Message: {payload_raw}")


# Start MQTT in a separate thread
def connect_mqtt():
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()  # Run in the background

threading.Thread(target=connect_mqtt, daemon=True).start()

# ------------------- DASHBOARD DASH -------------------
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Dashboard do Alvik - Sensores", style={"textAlign": "center", "color": "white"}),

    html.Div([
        html.Div([dcc.Graph(id="sensor-graph")], className="six columns"),
        html.Div([
            html.H3(f"Sensores Ativados (>{baseline}):", style={"color": "white"}),
            html.Ul(id="sensor-status", style={"fontSize": "20px", "color": "red"})
        ], className="six columns"),
    ], className="row"),

    html.Div([
        html.Div([dcc.Graph(id="accel-graph")], className="six columns"),
        html.Div([dcc.Graph(id="gyro-graph")], className="six columns"),
    ], className="row"),

    html.Div([
        html.Div([dcc.Graph(id="pose-graph")], className="six columns"),
        html.Div([dcc.Graph(id="gyro-3d-graph")], className="six columns"),
    ], className="row"),

    html.Div([
        html.Div([dcc.Graph(id="speed-graph")], className="six columns"),
    ], className="row"),

    dcc.Interval(id="interval-component", interval=1000, n_intervals=0)  # Update every second
], style={"backgroundColor": "black", "color": "white"})

# ------------------- CALLBACKS -------------------

# Function to generate line plots
def generate_line_plot(title, x_data, y_data, y_label):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_data, y=y_data, mode="lines", name=title))
    fig.update_layout(title=title, xaxis_title="Time", yaxis_title=y_label,
                      template="plotly_dark", plot_bgcolor="black", paper_bgcolor="black")
    return fig

# Update Sensor Graph (Left, Center, Right)
@app.callback(Output("sensor-graph", "figure"), Input("interval-component", "n_intervals"))
def update_sensor_graph(_):
    if not data["timestamp"]:
        return go.Figure()

    return generate_line_plot("Sensor Readings", data["timestamp"], [data["left"], data["center"], data["right"]], "Sensor Values")

# Update Accelerometer Graph
@app.callback(Output("accel-graph", "figure"), Input("interval-component", "n_intervals"))
def update_accel_graph(_):
    if not data["timestamp"]:
        return go.Figure()

    return generate_line_plot("Accelerometer Data", data["timestamp"], [data["accel_x"], data["accel_y"], data["accel_z"]], "Acceleration")

# Update Gyroscope Graph
@app.callback(Output("gyro-graph", "figure"), Input("interval-component", "n_intervals"))
def update_gyro_graph(_):
    if not data["timestamp"]:
        return go.Figure()

    return generate_line_plot("Gyroscope Data", data["timestamp"], [data["gyro_x"], data["gyro_y"], data["gyro_z"]], "Rotation Speed")

# Update Pose Graph (X, Y)
@app.callback(Output("pose-graph", "figure"), Input("interval-component", "n_intervals"))
def update_pose_graph(_):
    if not data["timestamp"]:
        return go.Figure()

    return generate_line_plot("Robot Pose", data["timestamp"], [data["pose_x"], data["pose_y"], data["pose_theta"]], "Position")

# Update Speed Graph
@app.callback(Output("speed-graph", "figure"), Input("interval-component", "n_intervals"))
def update_speed_graph(_):
    if not data["timestamp"]:
        return go.Figure()

    return generate_line_plot("Wheel Speed", data["timestamp"], [data["speed_left"], data["speed_right"]], "Speed")

# Update Gyroscope 3D Visualization
@app.callback(Output("gyro-3d-graph", "figure"), Input("interval-component", "n_intervals"))
def update_gyro_3d_graph(_):
    if not data["timestamp"]:
        return go.Figure()

    latest_idx = -1
    x, y, z = data["gyro_x"][latest_idx], data["gyro_y"][latest_idx], data["gyro_z"][latest_idx]

    fig = go.Figure(data=[go.Scatter3d(
        x=[0, x], y=[0, y], z=[0, z], mode="lines", marker=dict(size=5, color="red")
    )])
    
    fig.update_layout(title="Gyroscope 3D Orientation", template="plotly_dark",
                      plot_bgcolor="black", paper_bgcolor="black",
                      scene=dict(xaxis_title="Gyro X", yaxis_title="Gyro Y", zaxis_title="Gyro Z"))
    return fig

# Update Active Sensors
@app.callback(Output("sensor-status", "children"), Input("interval-component", "n_intervals"))
def update_sensor_status(_):
    return [html.Li(sensor, style={"color": "red"}) for sensor in sensor_alerts] if sensor_alerts else [html.Li("No sensors above threshold", style={"color": "green"})]

if __name__ == "__main__":
    app.run_server(debug=True, port=8080)
