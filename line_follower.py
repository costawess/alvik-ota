from arduino_alvik import ArduinoAlvik
from time import sleep_ms
import sys

def calculate_center(left: int, center: int, right: int):
    centroid = 0
    sum_weight = left + center + right
    sum_values = left + 2 * center + 3 * right
    if sum_weight != 0:
        centroid = sum_values / sum_weight
        centroid = 2 - centroid
    return centroid

alvik = ArduinoAlvik()
alvik.begin()

kp = 60.0
kd = 15.0
base_speed = 30
line_threshold = 250  # threshold for detecting the line
last_error = 0.0  # Initialize last_error for PD control

alvik.left_led.set_color(0, 0, 1)
alvik.right_led.set_color(0, 0, 1)

# Wait for the start button to be pressed
while alvik.get_touch_ok():
    sleep_ms(50)

while not alvik.get_touch_ok():
    sleep_ms(50)

try:
    while True:
        # Main loop to check if the stop button is pressed
        while not alvik.get_touch_cancel():
            line_sensors = alvik.get_line_sensors()
            left, center, right = line_sensors  # Split into three variables

            # Detect 90-degree turn to the left
            if left > line_threshold and center < line_threshold and right < line_threshold:
                # Turn left until the center sensor detects the line again
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
                control = (error * kp) + (derivative * kd)

                left_speed = max(0, min(base_speed - control, 60))
                right_speed = max(0, min(base_speed + control, 60))

                alvik.set_wheels_speed(left_speed, right_speed)

                if abs(control) > 0.2:
                    alvik.left_led.set_color(1, 0, 0)  # Red indicates correction
                    alvik.right_led.set_color(0, 0, 0)
                else:
                    alvik.left_led.set_color(0, 1, 0)  # Green indicates centered
                    alvik.right_led.set_color(0, 1, 0)

            sleep_ms(100)

        # Reset after stop button is pressed
        while not alvik.get_touch_ok():
            alvik.left_led.set_color(0, 0, 1)
            alvik.right_led.set_color(0, 0, 1)
            alvik.brake()
            sleep_ms(100)

except KeyboardInterrupt:
    print('Program interrupted')
    alvik.stop()
    sys.exit()
