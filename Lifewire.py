#libraries
from board import A1, GP20, GP21, GP28, GP25
from digitalio import DigitalInOut, Direction 
from analogio import AnalogIn, AnalogOut 
from neopixel import NeoPixel
from time import monotonic as now
import pwmio
import array
import math

#classes
class Button:
    def __init__(self, pin, interval=0.01):
        self.input = DigitalInOut(pin)
        self.input.direction = Direction.INPUT
        self.last_state = not self.input.value
        self.interval = interval
        self.last_time = now()
        
    def poll(self):
        current_state = not self.input.value
        if (now() - self.last_time) > self.interval:
            if not self.last_state and current_state:
                self.last_state = current_state
                self.last_time = now()
                return "Pressed"
            if self.last_state and not current_state:
                self.last_state = current_state
                self.last_time = now()
                return "Released"
        return None

class BPMCalculator:
    def __init__(self):
        self.blink_count = 0
        self.start_time = now()
        
    def add_blink(self):
        self.blink_count += 1
        
    def calculate_bpm(self):
        current_time = now()
        elapsed_time = current_time - self.start_time
        
        if elapsed_time >= 30:
            bpm = self.blink_count * 2
            self.start_time = current_time
            self.blink_count = 0
            return bpm
        return None

class LEDController:
    def __init__(self, led_pin):
        # Main LED setup
        self.led = DigitalInOut(led_pin)
        self.led.direction = Direction.OUTPUT
        
        # NeoPixel setup
        self.pixel = NeoPixel(GP28, 1)  # Initialize NeoPixel on GP28
        
        self.LED_ON_TIME = 0.1
        self.last_blink_time = 0
        self.is_abnormal = False
        
    def blink(self):
        self.led.value = True
        self.last_blink_time = now()
        
    def update(self, current_time):
        if self.led.value and (current_time - self.last_blink_time >= self.LED_ON_TIME):
            self.led.value = False
            
    def set_warning(self, is_abnormal):
        self.is_abnormal = is_abnormal
        if is_abnormal:
            self.pixel[0] = (255, 0, 0)  # Red (using NeoPixel for red)
            self.led.value = False
        else:
            self.pixel[0] = (0, 0, 0)  # Off (turn off the NeoPixel)
            
    def turn_off_all(self):
        self.led.value = False
        self.pixel[0] = (0, 0, 0)  # Turn off NeoPixel

class SensitiveEMGDetector:
    def __init__(self, sensor_pin, led_pin, button_pin):
        # Sensor setup
        self.sensor = AnalogIn(sensor_pin)
        
        # Initialize LED controller, BPM calculator, and button
        self.led_controller = LEDController(led_pin)
        self.bpm_calculator = BPMCalculator()
        self.button = Button(button_pin)
        
        # Detection state
        self.is_running = True
        
        # Buffer for moving average
        self.BUFFER_SIZE = 4
        self.buffer = array.array('H', [0] * self.BUFFER_SIZE)
        self.buffer_index = 0
        self.SHOW_VALUE = False
        
        # Timing controls
        self.MEASURE_TIME = 1.0 / 25
        self.last_measure_time = now()
        self.MIN_BEAT_INTERVAL = 0.4
        self.blink_cooldown = 0.2
        self.last_beat_time = 0
        
        # Dynamic threshold settings
        self.dynamic_window_size = 25
        self.threshold_factor = 0.9
        
        # State variables
        self.rising = False
        self.peak_detected = False
        self.last_value = 0

    def get_filtered_reading(self):
        self.buffer[self.buffer_index] = self.sensor.value
        self.buffer_index = (self.buffer_index + 1) % self.BUFFER_SIZE
        return sum(self.buffer) // self.BUFFER_SIZE

    def calculate_std_dev(self, readings, mean):
        variance = sum((x - mean) ** 2 for x in readings) / len(readings)
        return math.sqrt(variance)

    def calculate_dynamic_threshold(self, recent_readings):
        mean = sum(recent_readings) / len(recent_readings)
        std_dev = self.calculate_std_dev(recent_readings, mean)
        return mean + self.threshold_factor * std_dev

    def toggle_detection(self):
        self.is_running = not self.is_running
        if not self.is_running:
            self.led_controller.turn_off_all()
            print("Detection stopped")
        else:
            print("Detection resumed")

    def run(self):
        print("Starting sensitive EMG detector...")
        print("Press GP20 button to toggle detection on/off")
        recent_readings = []
        
        while True:
            button_state = self.button.poll()
            if button_state == "Pressed":
                self.toggle_detection()
                
            if not self.is_running:
                continue
                
            current_time = now()
            
            if current_time - self.last_measure_time >= self.MEASURE_TIME:
                self.last_measure_time = current_time
                value = self.get_filtered_reading()
                if self.SHOW_VALUE:
                    print(f"value: {value}")
            
                recent_readings.append(value)
                if len(recent_readings) > self.dynamic_window_size:
                    recent_readings.pop(0)

                threshold = self.calculate_dynamic_threshold(recent_readings)
            
                if current_time - self.last_beat_time < self.blink_cooldown:
                    continue
            
                if value > threshold and not self.rising:
                    self.rising = True
            
                if self.rising and value < self.last_value:
                    if current_time - self.last_beat_time >= self.MIN_BEAT_INTERVAL and not self.peak_detected:
                        self.led_controller.blink()
                        self.last_beat_time = current_time
                        self.peak_detected = True
                        self.bpm_calculator.add_blink()
                        print("Peak detected! LED blinking.")
            
                if value < threshold - 100:
                    self.rising = False
                    self.peak_detected = False
            
                self.last_value = value
                
                self.led_controller.update(current_time)
                
                bpm = self.bpm_calculator.calculate_bpm()
                if bpm is not None:
                    print(f"BPM: {bpm}")
                    is_abnormal = bpm < 50 or bpm > 90
                    self.led_controller.set_warning(is_abnormal)
                    if is_abnormal:
                        print("BPM is out of range! RGB LED is red.")
                    else:
                        print("BPM is normal. RGB LED is off.")

def main():
    LED = GP25
    detector = SensitiveEMGDetector(
        sensor_pin=A1,
        led_pin=LED,
        button_pin=GP20
    )
    detector.run()

if __name__ == "__main__":
    main()