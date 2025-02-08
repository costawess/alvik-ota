from arduino_alvik import ArduinoAlvik
from time import sleep_ms
import sys
import network
from umqtt.simple import MQTTClient
from time import time

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

            # get accel data and gyro data
            accel_data = alvik.get_accelerations()
            gyro_data = alvik.get_gyros()
            speed = alvik.get_wheels_speed()
            pose = alvik.get_pose()
            # servo_pos = alvik.get_servo_positions()  # Define servo_pos

            # Publica os dados dos sensores no MQTT
            timestamp = int(time())
            payload = (
                f'{{"timestamp": {timestamp}, '
                f'"left": {left}, '
                f'"center": {center}, '
                f'"right": {right}, '
                f'"accel_x": {accel_data[0]}, '
                f'"accel_y": {accel_data[1]}, '
                f'"accel_z": {accel_data[2]}, '
                f'"gyro_x": {gyro_data[0]}, '
                f'"gyro_y": {gyro_data[1]}, '
                f'"gyro_z": {gyro_data[2]}, '
                f'"speed": {speed}, '
                f'"pose_x": {pose[0]}, '
                f'"pose_y": {pose[1]}, '
                f'"pose_theta": {pose[2]}}}'
            )
            try:
                client.publish(MQTT_TOPIC, payload)
                print("📡 Enviado MQTT:", payload)
            except Exception as e:
                print("⚠ Erro ao publicar MQTT:", e)
                connect_mqtt()  # Reconectar se perder conexão

            # **1. CURVA ACENTUADA PARA A ESQUERDA (90°)**
            if left > LINE_THRESHOLD and center < LINE_THRESHOLD and right < LINE_THRESHOLD:
                alvik.set_wheels_speed(-TURN_SPEED, TURN_SPEED)
                while alvik.get_line_sensors()[1] < LINE_THRESHOLD:
                    sleep_ms(10)

            # **2. CURVA ACENTUADA PARA A DIREITA (90°)**
            elif right > LINE_THRESHOLD and center < LINE_THRESHOLD and left < LINE_THRESHOLD:
                alvik.set_wheels_speed(TURN_SPEED, -TURN_SPEED)
                while alvik.get_line_sensors()[1] < LINE_THRESHOLD:
                    sleep_ms(10)

            # **3. LEVE AJUSTE PARA A ESQUERDA**
            elif left > SLOW_DOWN_THRESHOLD and center > LINE_THRESHOLD and right < LINE_THRESHOLD:
                alvik.set_wheels_speed(BASE_SPEED // 2, BASE_SPEED)

            # **4. LEVE AJUSTE PARA A DIREITA**
            elif right > SLOW_DOWN_THRESHOLD and center > LINE_THRESHOLD and left < LINE_THRESHOLD:
                alvik.set_wheels_speed(BASE_SPEED, BASE_SPEED // 2)

            # **5. LINHA CENTRALIZADA → SEGUE EM FRENTE**
            elif center > LINE_THRESHOLD:
                alvik.set_wheels_speed(BASE_SPEED, BASE_SPEED)

            # **6. LINHA PERDIDA → PARE PARA REENCONTRAR**
            else:
                alvik.set_wheels_speed(-10, -10)  # Dá um pequeno passo para trás
                sleep_ms(100)
                alvik.set_wheels_speed(0, 0)  # Para completamente
                sleep_ms(100)

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
