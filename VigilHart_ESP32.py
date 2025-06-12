from machine import ADC
import time
import array
import math

class BPMCalculator:
    def __init__(self):
        self.blink_count = 0
        self.start_time = time.ticks_ms()
        
    def add_blink(self):
        self.blink_count += 1
        
    def calculate_bpm(self):
        current_time = time.ticks_ms()
        elapsed_ms = time.ticks_diff(current_time, self.start_time)
        
        if elapsed_ms >= 10000:  # 10 seconds window
            bpm = (self.blink_count * 60 * 1000) / elapsed_ms
            self.start_time = current_time
            self.blink_count = 0
            return int(bpm)
        return None

class EMGDetector:
    def __init__(self, sensor_pin):
        self.sensor = ADC(sensor_pin)
        self.sensor.atten(ADC.ATTN_11DB)  # Full range 0-3.3V

        self.BUFFER_SIZE = 4
        self.buffer = array.array('H', [0]*self.BUFFER_SIZE)
        self.buffer_index = 0

        self.dynamic_window_size = 25
        self.threshold_factor = 0.9
        self.recent_readings = []

        self.last_measure_time = time.ticks_ms()
        self.MEASURE_INTERVAL_MS = 40  # 25Hz sampling

        self.MIN_BEAT_INTERVAL_MS = 400
        self.blink_cooldown_ms = 200

        self.last_beat_time = 0
        self.rising = False
        self.peak_detected = False
        self.last_value = 0

        self.bpm_calculator = BPMCalculator()

    def get_filtered_reading(self):
        val = self.sensor.read() * 16  # scale 0-4095 to 0-65520
        self.buffer[self.buffer_index] = val
        self.buffer_index = (self.buffer_index + 1) % self.BUFFER_SIZE
        return sum(self.buffer) // self.BUFFER_SIZE

    def calculate_std_dev(self, readings, mean):
        variance = sum((x - mean) ** 2 for x in readings) / len(readings)
        return math.sqrt(variance)

    def calculate_dynamic_threshold(self, recent_readings):
        mean = sum(recent_readings) / len(recent_readings)
        std_dev = self.calculate_std_dev(recent_readings, mean)
        return mean + self.threshold_factor * std_dev

    def run(self):
        print("Starting EMG heart rate detection...")
        while True:
            current_time = time.ticks_ms()
            if time.ticks_diff(current_time, self.last_measure_time) >= self.MEASURE_INTERVAL_MS:
                self.last_measure_time = current_time

                value = self.get_filtered_reading()
                self.recent_readings.append(value)
                if len(self.recent_readings) > self.dynamic_window_size:
                    self.recent_readings.pop(0)

                threshold = self.calculate_dynamic_threshold(self.recent_readings)

                if time.ticks_diff(current_time, self.last_beat_time) < self.blink_cooldown_ms:
                    continue

                if value > threshold and not self.rising:
                    self.rising = True

                if self.rising and value < self.last_value:
                    if (time.ticks_diff(current_time, self.last_beat_time) >= self.MIN_BEAT_INTERVAL_MS
                        and not self.peak_detected):
                        self.last_beat_time = current_time
                        self.peak_detected = True
                        self.bpm_calculator.add_blink()
                        print("Peak detected")

                if value < threshold - 100:
                    self.rising = False
                    self.peak_detected = False

                self.last_value = value

                bpm = self.bpm_calculator.calculate_bpm()
                if bpm is not None:
                    print(f"BPM: {bpm}")

def main():
    detector = EMGDetector(sensor_pin=34)  # change 34 to your ADC pin
    detector.run()

if __name__ == "__main__":
    main()
