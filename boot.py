# This file is executed when the ESP32 starts.
try:
    import utime as time
except:
    import time


if __name__ == "__main__":
    import util

    util.led_rgb.red()

    while True:
        util.led_yellow.on()
        time.sleep(1)
        util.led_yellow.off()
        time.sleep(0.5)
