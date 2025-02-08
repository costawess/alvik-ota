import json
from arduino_alvik import ArduinoAlvik
from time import sleep_ms, time
import sys
import network
from umqtt.simple import MQTTClient

# ------------------- CONFIGURAÇÃO MQTT -------------------
MQTT_BROKER = "192.168.2.14"  # Substitua pelo endereço do seu broker MQTT
MQTT_TOPIC = "alvik/sensors"
MQTT_CLIENT_ID = "Alvik_Robot"

# Inicializa Wi-Fi e MQTT
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect("H369AE3F1EF", "CC726D5CED93")  # Substitua pelo seu Wi-Fi
    while not wlan.isconnected():
        print("Conectando ao Wi-Fi...")
        sleep_ms(500)
    print("✅ Conectado ao Wi-Fi:", wlan.ifconfig())

def connect_mqtt():
    global client
    client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER)
    try:
        client.connect()
        print("✅ Conectado ao MQTT Broker!")
    except Exception as e:
        print("❌ Erro ao conectar ao MQTT:", e)
        sys.exit()

# ------------------- CONFIGURAÇÃO DO ROBÔ -------------------
alvik = ArduinoAlvik()
alvik.begin()

# Parâmetros de velocidade e sensores
BASE_SPEED = 20       # Velocidade base do robô
TURN_SPEED = 15       # Velocidade para curvas
LINE_THRESHOLD = 250  # Limite de detecção da linha preta
SLOW_DOWN_THRESHOLD = 400  # Sensibilidade extra para ajustes finos

# Indicar que o robô está pronto para iniciar
alvik.left_led.set_color(0, 0, 1)  # Azul
alvik.right_led.set_color(0, 0, 1)

# Conectar Wi-Fi e MQTT
connect_wifi()
connect_mqtt()

# Aguarda o botão de início ser pressionado
while alvik.get_touch_ok():
    sleep_ms(50)

while not alvik.get_touch_ok():
    sleep_ms(50)

try:
    while True:
        # Aguarda até que o botão de parada seja pressionado
        while not alvik.get_touch_cancel():
            left, center, right = alvik.get_line_sensors()  # Lê os sensores
            accel_data = alvik.get_accelerations()
            gyro_data = alvik.get_gyros()
            speed = alvik.get_wheels_speed()
            pose = alvik.get_pose()

            # Convert tuple speed to list ✅
            speed_list = list(speed)

            # Generate a valid JSON payload ✅
            payload = {
                "timestamp": int(time()),
                "left": left,
                "center": center,
                "right": right,
                "accel_x": accel_data[0],
                "accel_y": accel_data[1],
                "accel_z": accel_data[2],
                "gyro_x": gyro_data[0],
                "gyro_y": gyro_data[1],
                "gyro_z": gyro_data[2],
                "speed": speed_list,  # ✅ Now it's a valid JSON list
                "pose_x": pose[0],
                "pose_y": pose[1],
                "pose_theta": pose[2]
            }

            # Convert payload to JSON string ✅
            json_payload = json.dumps(payload)

            try:
                client.publish(MQTT_TOPIC, json_payload)
                print("📡 Enviado MQTT:", json_payload)
            except Exception as e:
                print("⚠ Erro ao publicar MQTT:", e)
                connect_mqtt()  # Reconectar se perder conexão

            sleep_ms(50)  # Pequena pausa para estabilidade

        # Reset após botão de parada
        while not alvik.get_touch_ok():
            alvik.left_led.set_color(0, 0, 1)  # Azul indicando que está aguardando
            alvik.right_led.set_color(0, 0, 1)
            alvik.brake()
            sleep_ms(100)

except KeyboardInterrupt:
    print('Program interrupted')
    alvik.stop()
    sys.exit()
