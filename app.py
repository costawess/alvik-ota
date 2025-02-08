import dash
from dash import dcc, html
import plotly.graph_objs as go
from dash.dependencies import Input, Output
import paho.mqtt.client as mqtt
import json
import threading
import time
import pandas as pd

# ------------------- CONFIGURAÇÃO MQTT -------------------
MQTT_BROKER = "192.168.2.14"  # IP do Broker MQTT
MQTT_TOPIC = "alvik/sensors"
GRAVITY = 9.81  # Conversion factor from g to m/s²

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
}

# MQTT Callback Function
import math

def on_message(client, _, msg):
    global data
    try:
        payload_raw = msg.payload.decode()
        payload = json.loads(payload_raw)  # Decode JSON
        timestamp = payload.get("timestamp", time.time())

        # Store new data points
        for key in data.keys():
            if key in payload:
                data[key].append(payload[key])

        # Normalize pose_theta (Yaw) to stay in [-180, 180] degrees
        if data["pose_theta"]:
            data["pose_theta"][-1] = (data["pose_theta"][-1] + 180) % 360 - 180

        # Convert Pose Theta from radians to degrees if needed
        if abs(data["pose_theta"][-1]) > 360:
            data["pose_theta"][-1] = math.degrees(data["pose_theta"][-1])

        # Ensure accelerometer is converted from g to m/s²
        if data["accel_x"]:
            data["accel_x"][-1] *= 9.81
            data["accel_y"][-1] *= 9.81
            data["accel_z"][-1] *= 9.81

        # Keep only the last 100 records to avoid overload
        for key in data.keys():
            data[key] = data[key][-100:]

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
        html.Div([dcc.Graph(id="accel-graph")], className="six columns"),
    ], className="row"),

    html.Div([
        html.Div([dcc.Graph(id="gyro-angles-graph")], className="six columns"),
        html.Div([dcc.Graph(id="pose-graph")], className="six columns"),
    ], className="row"),

    dcc.Interval(id="interval-component", interval=1000, n_intervals=0)  # Update every second
], style={"backgroundColor": "black", "color": "white"})

# ------------------- CALLBACKS -------------------

# Function to generate line plots
def generate_line_plot(title, x_data, y_data, y_labels):
    fig = go.Figure()
    for y, label in zip(y_data, y_labels):
        fig.add_trace(go.Scatter(x=x_data, y=y, mode="lines", name=label))

    fig.update_layout(title=title, xaxis_title="Time", yaxis_title="Values",
                      template="plotly_dark", plot_bgcolor="black", paper_bgcolor="black")
    return fig

# Update Sensor Graph (Left, Center, Right)
@app.callback(Output("sensor-graph", "figure"), Input("interval-component", "n_intervals"))
def update_sensor_graph(_):
    if not data["timestamp"]:
        return go.Figure()

    return generate_line_plot(
        "Line Sensors", data["timestamp"], 
        [data["left"], data["center"], data["right"]],
        ["Left", "Center", "Right"]
    )

# Update Accelerometer Graph (X, Y, Z in m/s²)
@app.callback(Output("accel-graph", "figure"), Input("interval-component", "n_intervals"))
def update_accel_graph(_):
    if not data["timestamp"]:
        return go.Figure()

    return generate_line_plot(
        "Acceleration (m/s²)", data["timestamp"], 
        [data["accel_x"], data["accel_y"], data["accel_z"]],
        ["Accel X", "Accel Y", "Accel Z"]
    )

# Update Gyro Angles (Yaw, Pitch, Roll)
@app.callback(Output("gyro-angles-graph", "figure"), Input("interval-component", "n_intervals"))
def update_gyro_angles_graph(_):
    if not data["timestamp"]:
        return go.Figure()

    return generate_line_plot(
        "Yaw, Pitch, Roll Angles", data["timestamp"], 
        [data["pose_theta"], data["gyro_y"], data["gyro_x"]],  # pose_theta (yaw), gyro_y (pitch), gyro_x (roll)
        ["Yaw (Theta)", "Pitch (Gyro Y)", "Roll (Gyro X)"]
    )

# Update Pose Graph (X, Y, Theta)
@app.callback(Output("pose-graph", "figure"), Input("interval-component", "n_intervals"))
def update_pose_graph(_):
    if not data["timestamp"]:
        return go.Figure()

    return generate_line_plot(
        "Robot Pose", data["timestamp"], 
        [data["pose_x"], data["pose_y"], data["pose_theta"]],
        ["Pose X", "Pose Y", "Pose Theta"]
    )

if __name__ == "__main__":
    app.run_server(debug=True, port=8080)
