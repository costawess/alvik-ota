import dash
from dash import dcc, html
import plotly.graph_objs as go
from dash.dependencies import Input, Output
import paho.mqtt.client as mqtt
import json
import threading
import time
import math
from datetime import datetime

# ------------------- CONFIGURAÇÃO MQTT -------------------
MQTT_BROKER = "192.168.2.14"  # IP do Broker MQTT
MQTT_TOPIC = "alvik/sensors"
GRAVITY = 9.81  # Convert g to m/s²

# Initialize global variables for yaw and time synchronization
yaw = 0.0
last_timestamp = None

# ------------------- Data Storage -------------------
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
    "yaw": [],
    "pitch": [],
    "roll": [],
}

# ------------------- Compute Angles -------------------
def compute_angles(accel_x, accel_y, accel_z, gyro_z, dt):
    global yaw

    # Compute Pitch and Roll using accelerometer
    pitch = math.degrees(math.atan2(-accel_x, math.sqrt(accel_y**2 + accel_z**2)))
    roll = math.degrees(math.atan2(accel_y, math.sqrt(accel_x**2 + accel_z**2)))

    # Integrate Gyro Z to estimate Yaw
    yaw += gyro_z * dt

    # Normalize Yaw to [-180, 180]
    yaw = (yaw + 180) % 360 - 180

    return pitch, roll, yaw

# ------------------- MQTT Callback Function -------------------
def on_message(client, _, msg):
    global data, last_timestamp

    try:
        payload_raw = msg.payload.decode()
        payload = json.loads(payload_raw)  # Decode JSON
        timestamp_str = payload.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))  # Convert timestamp

        # Ensure time updates happen at 1-second intervals
        if last_timestamp is None:
            last_timestamp = timestamp_str

        dt = 1  # Fix sampling interval to 1 sec
        last_timestamp = timestamp_str

        # Convert accelerometer values from g to m/s²
        accel_x = -payload.get("accel_x", 0) * GRAVITY
        accel_y = -payload.get("accel_y", 0) * GRAVITY
        accel_z = -payload.get("accel_z", 0) * GRAVITY
        gyro_z = payload.get("gyro_z", 0)

        # Compute angles
        pitch, roll, yaw_value = compute_angles(accel_x, accel_y, accel_z, gyro_z, dt)

        # Store new data points
        for key in data.keys():
            if key in payload:
                data[key].append(payload[key])
            else:
                # Fill missing values with last known or zero
                data[key].append(data[key][-1] if data[key] else 0)

        # Store computed angles
        data["pitch"].append(pitch)
        data["roll"].append(roll)
        data["yaw"].append(yaw_value)

        # Store timestamp
        data["timestamp"].append(timestamp_str)

        # Keep only the last 100 records to avoid overload
        for key in data.keys():
            data[key] = data[key][-100:]

    except json.JSONDecodeError as e:
        print(f"❌ JSON Decode Error: {e} - Raw Message: {payload_raw}")

# ------------------- Start MQTT in a Separate Thread -------------------
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
    
    # Convert timestamps to datetime format for proper x-axis formatting
    x_data = [datetime.strptime(t, "%Y-%m-%d %H:%M:%S") for t in x_data]

    for y, label in zip(y_data, y_labels):
        fig.add_trace(go.Scatter(x=x_data, y=y, mode="lines", name=label))

    if title == "Yaw, Pitch, Roll Angles":
        fig.update_yaxes(range=[-180, 180])
    fig.update_layout(title=title, xaxis_title="Time", yaxis_title="Values",
                      template="plotly_dark", plot_bgcolor="black", paper_bgcolor="black",
                      xaxis=dict(tickformat="%H:%M:%S"))  # Show time in HH:MM:SS format
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

# Update Gyro Angles (Yaw, Pitch, Roll) from MQTT Data
@app.callback(Output("gyro-angles-graph", "figure"), Input("interval-component", "n_intervals"))
def update_gyro_angles_graph(_):
    if not data["timestamp"]:
        return go.Figure()

    return generate_line_plot(
        "Yaw, Pitch, Roll Angles", data["timestamp"], 
        [data["yaw"], data["pitch"], data["roll"]],  
        ["Yaw (Theta)", "Pitch", "Roll"]
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
