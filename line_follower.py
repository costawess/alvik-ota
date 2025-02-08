import json
from arduino_alvik import ArduinoAlvik
from time import sleep_ms, time
import sys
import network
from math import atan2, sqrt
from umqtt.simple import MQTTClient

# ------------------- CONFIGURAÇÃO MQTT -------------------
MQTT_BROKER = "192.168.2.14"  # IP do Broker MQTT
MQTT_TOPIC = "alvik/sensors"
MQTT_CLIENT_ID = "Alvik_Robot"

# ------------------- CONEXÃO WI-FI -------------------
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect("H369AE3F1EF", "CC726D5CED93")  # Substitua pelo seu Wi-Fi
    while not wlan.isconnected():
        print("Conectando ao Wi-Fi...")
        sleep_ms(500)
    print("✅ Conectado ao Wi-Fi:", wlan.ifconfig())

# ------------------- CONEXÃO MQTT -------------------
def connect_mqtt():
    global client
    client = MQTTClient(MQTT_CLIENT_ID, MQTT_BROKER)
    try:
        client.connect()
        print("✅ Conectado ao MQTT Broker!")
    except Exception as e:
        print("❌ Erro ao conectar ao MQTT:", e)
        sys.exit()

def calculate_orientation(accel_data):
    accel_x, accel_y, accel_z = accel_data

    # Roll: rotação em torno do eixo X
    roll = atan2(accel_y, accel_z)

    # Pitch: rotação em torno do eixo Y
    pitch = atan2(-accel_x, sqrt(accel_y**2 + accel_z**2))

    # Yaw não pode ser calculado apenas com o acelerômetro
    yaw = 0  # Placeholder, pois é necessário um magnetômetro para calcular o yaw

    return yaw, pitch, roll

# ------------------- CONFIGURAÇÃO DO ROBÔ -------------------
alvik = ArduinoAlvik()
alvik.begin()

# Parâmetros do robô
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

# ------------------- LOOP PRINCIPAL -------------------
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

            yaw, pitch, roll = calculate_orientation(accel_data)

            # Convert tuple speed to list ✅
            speed_list = list(speed)

            # Criar o payload JSON corretamente ✅
            payload = {
                "timestamp": time(),  # Save the time in normal format
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
                "pose_theta": pose[2],
                "yaw": yaw,
                "pitch": pitch,
                "roll": roll
            }

            # Converter para JSON
            json_payload = json.dumps(payload)

            # Publicar no MQTT
            try:
                client.publish(MQTT_TOPIC, json_payload)
                print("📡 Enviado MQTT:", json_payload)
            except Exception as e:
                print("⚠ Erro ao publicar MQTT:", e)
                connect_mqtt()  # Reconectar MQTT se perder conexão

            # ------------------- LÓGICA DE SEGUIR A LINHA -------------------
            if left > LINE_THRESHOLD and center < LINE_THRESHOLD and right < LINE_THRESHOLD:
                # Curva acentuada à esquerda
                alvik.set_wheels_speed(-TURN_SPEED, TURN_SPEED)
                while alvik.get_line_sensors()[1] < LINE_THRESHOLD:
                    sleep_ms(10)

            elif right > LINE_THRESHOLD and center < LINE_THRESHOLD and left < LINE_THRESHOLD:
                # Curva acentuada à direita
                alvik.set_wheels_speed(TURN_SPEED, -TURN_SPEED)
                while alvik.get_line_sensors()[1] < LINE_THRESHOLD:
                    sleep_ms(10)

            elif left > SLOW_DOWN_THRESHOLD and center > LINE_THRESHOLD and right < LINE_THRESHOLD:
                # Ajuste leve à esquerda
                alvik.set_wheels_speed(BASE_SPEED // 2, BASE_SPEED)

            elif right > SLOW_DOWN_THRESHOLD and center > LINE_THRESHOLD and left < LINE_THRESHOLD:
                # Ajuste leve à direita
                alvik.set_wheels_speed(BASE_SPEED, BASE_SPEED // 2)

            elif center > LINE_THRESHOLD:
                # Seguir em frente
                alvik.set_wheels_speed(BASE_SPEED, BASE_SPEED)

            else:
                # Parar e procurar a linha
                alvik.set_wheels_speed(-10, -10)
                sleep_ms(100)
                alvik.set_wheels_speed(0, 0)
                sleep_ms(100)

            sleep_ms(50)  # Pequena pausa para estabilidade

        # Reset após botão de parada
        while not alvik.get_touch_ok():
            alvik.left_led.set_color(0, 0, 1)  # Azul indicando que está aguardando
            alvik.right_led.set_color(0, 0, 1)
            alvik.brake()
            sleep_ms(100)

except KeyboardInterrupt:
    print('❌ Programa interrompido')
    alvik.stop()
    sys.exit()
