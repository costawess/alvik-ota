from arduino_alvik import ArduinoAlvik
from time import sleep_ms
import sys

# Inicializa o robô Alvik
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