import json
from arduino_alvik import ArduinoAlvik
from time import sleep_ms, time, localtime, strftime
import sys
import network
from math import atan2, sqrt
from umqtt.simple import MQTTClient
import ntptime



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

    # Sincronizar o relógio com o servidor NTP
    try:
        ntptime.settime()
        # Ajustar para o fuso horário de Amsterdã (UTC+1 ou UTC+2 com horário de verão)
        tm = localtime()
        offset = 2 if tm.tm_isdst > 0 else 1
        adjusted_time = time() + offset * 3600
        localtime(adjusted_time)
        print("✅ Relógio sincronizado com o servidor NTP")
    except Exception as e:
        print("⚠ Erro ao sincronizar o relógio com o servidor NTP:", e)

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

# ------------------- FUNÇÃO PARA CALCULAR ORIENTAÇÃO -------------------
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

# Indicar que o robô está pronto para iniciar
alvik.left_led.set_color(1, 0.5, 0)  # Laranja
alvik.right_led.set_color(1, 0.5, 0)

# Parâmetros do robô
BASE_SPEED = 20       # Velocidade base do robô
TURN_SPEED = 15       # Velocidade para curvas
LINE_THRESHOLD = 250  # Limite de detecção da linha preta
SLOW_DOWN_THRESHOLD = 400  # Sensibilidade extra para ajustes finos

# Indicar que o robô está pronto para iniciar
alvik.left_led.set_color(0, 1, 0)  # Verde
alvik.right_led.set_color(0, 1, 0)

# Conectar Wi-Fi e MQTT
connect_wifi()
connect_mqtt()

# Inicializar tempo da última publicação MQTT
last_publish_time = time()

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

            # Publicar no MQTT a cada meio segundo
            current_time = time()
            if current_time - last_publish_time >= 0.5:
                accel_data = alvik.get_accelerations()
                gyro_data = alvik.get_gyros()
                speed = alvik.get_wheels_speed()
                pose = alvik.get_pose()

                yaw, pitch, roll = calculate_orientation(accel_data)

                # Convert tuple speed to list ✅
                speed_list = list(speed)

                # Obter timestamp em formato ISO 8601 ✅
                timestamp_str = strftime("%Y-%m-%d %H:%M:%S", localtime(current_time))

                # Criar o payload JSON corretamente ✅
                payload = {
                    "timestamp": timestamp_str,  # Use full date-time format
                    "left": left,
                    "center": center,
                    "right": right,
                    "accel_x": round(accel_data[0], 4),  # Ensure float precision
                    "accel_y": round(accel_data[1], 4),
                    "accel_z": round(accel_data[2], 4),
                    "gyro_x": round(gyro_data[0], 4),
                    "gyro_y": round(gyro_data[1], 4),
                    "gyro_z": round(gyro_data[2], 4),
                    "speed": speed_list,  # ✅ Now it's a valid JSON list
                    "pose_x": round(pose[0], 4),
                    "pose_y": round(pose[1], 4),
                    "pose_theta": round(pose[2], 4),
                    "yaw": round(yaw, 4),
                    "pitch": round(pitch, 4),
                    "roll": round(roll, 4)
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

                last_publish_time = current_time

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
