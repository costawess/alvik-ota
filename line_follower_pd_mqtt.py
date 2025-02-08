from arduino_alvik import ArduinoAlvik
import sys

# Connectivity libraries
import network
from umqtt.simple import MQTTClient
import json

# time library
import time
from time import sleep_ms

# ---------------------------------------------------------------------
# FUNCTIONS

def promptMessage(message):
    print(message)
    input("Press enter to continue...")

# Connect to WiFi
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    while not wlan.isconnected():
        print("Connecting to WiFi...")
        time.sleep(1)
    print("Connected to WiFi")

# Connect to MQTT Broker
def connect_mqtt():
    client = MQTTClient("client_id", MQTT_BROKER, port=MQTT_PORT)
    client.connect()
    print("Connected to MQTT Broker")
    return client

# Send MQTT message
def send_message(client, message):
    client.publish(MQTT_TOPIC, message)
    print(f"Message '{message}' sent to topic '{MQTT_TOPIC}'")

# Define a callback function to handle incoming MQTT messages
def mqtt_callback(topic, msg):
    global kp, ki, kd
    try:
        # Decode the message and parse the JSON
        data = json.loads(msg.decode())
        
        # Update PID constants if they are in the message
        if 'kp' in data:
            kp = data['kp']
        if 'ki' in data:
            ki = data['ki']
        if 'kd' in data:
            kd = data['kd']
        
        print(f"Updated PID constants: kp={kp}, ki={ki}, kd={kd}")
    except Exception as e:
        print(f"Failed to update PID constants: {e}")


# ---------------------------------------------------------------------
# PARAMETERS
USE_MQTT = True  # Set to False if you do not want to connect to WiFi/MQTT

# WiFi credentials
SSID     = "EwoutBergsma"
PASSWORD = "EwoutBergsma"

# MQTT broker details
MQTT_BROKER = "192.168.0.131"  # Replace with your broker address if different
MQTT_PORT   = 1883
MQTT_TOPIC  = "alvik"

# ---------------------------------------------------------------------
# Initialize WiFi/MQTT connection based on flag
client = None
if USE_MQTT:
    connect_wifi()
    client = connect_mqtt()

# Function to calculate the centroid position from line sensor readings
def calculate_center(left: int, center: int, right: int):
    centroid = 0
    sum_weight = left + center + right
    sum_values = left + 2 * center + 3 * right
    if sum_weight != 0:
        centroid = sum_values / sum_weight
        centroid = 2 - centroid
    return centroid

# ---------------------------------------------------------------------
# MAIN CODE
alvik = ArduinoAlvik()
alvik.begin()

kp = 60.0
kd = 15.0
base_speed = 25 
line_threshold = 250  # threshold for detecting the line
last_error = 0

alvik.left_led.set_color(0, 0, 1)
alvik.right_led.set_color(0, 0, 1)

print('Waiting for start button...')

while alvik.get_touch_ok():
    print('PRESSED...')
    sleep_ms(50)

while not alvik.get_touch_ok():
    sleep_ms(50)

print('Starting...')

try:
    while True:
        while not alvik.get_touch_cancel():

            # Set the MQTT callback
            client.set_callback(mqtt_callback)
            client.subscribe(MQTT_TOPIC)
            client.check_msg()
          
            # Read the ToF sensor
            L, CL, C, CR, R = alvik.get_distance()
            T = alvik.get_distance_top()
            B = alvik.get_distance_bottom()
            print(f'T: {T} | B: {B} | L: {L} | CL: {CL} | C: {C} | CR: {CR} | R: {R}')

            line_sensors = alvik.get_line_sensors()
            left, center, right = line_sensors # Split into three variables
          

            # Detect 90-degree turn to the left
            if left > line_threshold and center < line_threshold and right < line_threshold:
                # Tunr left until the center sensor detects the line again
                alvik.set_wheels_speed(-15, 15)
                while alvik.get_line_sensors()[1] < line_threshold:
                    sleep_ms(10)

            # Detect 90-degree turn to the right
            elif right > line_threshold and center < line_threshold and left < line_threshold:
                # Turn right until the center sensor detects the line again
                alvik.set_wheels_speed(15, -15)
                while alvik.get_line_sensors()[1] < line_threshold:
                    sleep_ms(10)

            else:
                # Normal line-following using PD
                error = calculate_center(left, center, right)
                
                derivative = error - last_error
                last_error = error
                kp_f = error * kp
                kd_f = derivative * kd
                control = kp_f + kd_f

                left_speed = max(0, min(base_speed - control, 60))
                right_speed = max(0, min(base_speed + control, 60))

                alvik.set_wheels_speed(left_speed, right_speed)

                if abs(control) > 0.2:
                    alvik.left_led.set_color(1, 0, 0)  # Red indicates correction
                    alvik.right_led.set_color(0, 0, 0)
                else:
                    alvik.left_led.set_color(0, 1, 0)  # Green indicates centered
                    alvik.right_led.set_color(0, 1, 0)
            
            # Prepare data to send over MQTT if enabled
            if USE_MQTT and client:
                data = {
                    "line_sensors": line_sensors,
                    "left_speed": left_speed,
                    "right_speed": right_speed,
                    "error": error,
                    "derivative": derivative,
                    "control": control,
                    "kp": kp,
                    "kd": kd,
                    "ToF_T": T,
                    "ToF_B": B,
                    "ToF_L": L,
                    "ToF_CL": CL,
                    "ToF_C": C,
                    "ToF_CR": CR,
                    "ToF_R": R,
                    "kp_f": kp_f,
                    "kd_f": kd_f
                    
                }

                # Convert to JSON string and publish
                message = json.dumps(data)
                send_message(client, message)

            # Update previous error for the next derivative calculation
            # prev_error = error
            last_error = error

            sleep_ms(100)

        # Reset after stop button is pressed
        while not alvik.get_touch_ok():
            alvik.left_led.set_color(0, 0, 1)
            alvik.right_led.set_color(0, 0, 1)
            alvik.brake()
            sleep_ms(100)

except KeyboardInterrupt as e:
    print('over')
    alvik.stop()
    sys.exit()

# ---------------------------------------------------------------------