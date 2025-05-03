from machine import Pin


class LED_YELLOW:
    def __init__(self) -> None:
        self.led = Pin(48, Pin.OUT)

    def on(self):
        self.led.value(1)

    def off(self):
        self.led.value(0)


class LED_RGB:
    def __init__(self) -> None:
        self.r = Pin(46, Pin.OUT)
        self.g = Pin(0, Pin.OUT)
        self.b = Pin(45, Pin.OUT)

    def on(self):
        self.r.value(0)
        self.g.value(0)
        self.b.value(0)

    def off(self):
        self.r.value(1)
        self.g.value(1)
        self.b.value(1)

    def red(self):
        self.off()
        self.r.value(0)

    def green(self):
        self.off()
        self.g.value(0)

    def blue(self):
        self.off()
        self.b.value(0)


led_yellow = LED_YELLOW()
led_rgb = LED_RGB()
