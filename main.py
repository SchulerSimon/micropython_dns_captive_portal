try:
    import utime as time
except:
    import time
try:
    import usys as sys
except:
    import sys

import gc

import util
import captive_portal


def submit(params):
    text = params.get(b"text", None)

    if text:
        print(text)

    headers = (
        b"HTTP/1.1 307 Temporary Redirect\r\n"
        b"Location: http://129.168.4.1/index.html\r\n"
    )

    return b"", headers


def main():
    util.led_rgb.red()
    cp = captive_portal.CaptivePortal()
    cp.setup(callback=submit)
    util.led_rgb.green()

    try:
        while True:
            util.led_yellow.on()
            gc.collect()
            time.sleep(0.1)
            cp.loop()
            util.led_yellow.off()
            time.sleep(0.01)

    except (Exception, KeyboardInterrupt) as e:
        sys.print_exception(e)
        print("Shutting down servers", e)

    util.led_rgb.red()
    cp.cleanup()


main()
# if __name__ == "__main__":
#     main()
