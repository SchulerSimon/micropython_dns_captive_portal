try:
    import ubinascii as binascii
except:
    import binascii
try:
    import utime as time
except:
    import time
try:
    import uselect as select
except:
    import select

import network

import dns_server
import http_server


class CaptivePortal:
    def __init__(self) -> None:
        self.ip = "192.168.4.1"
        self.ssid = "SimonsESP32"
        self.password = None

        # default values
        self.ap = None
        self.dns_server = None
        self.http_server = None

        self.poller = select.poll()

    def setup(self, callback) -> None:
        # configure the ap
        self.ap = network.WLAN(network.AP_IF)
        self.ap.active(True)
        if self.password:
            self.ap.config(essid=self.ssid, password=self.password)
        else:
            self.ap.config(essid=self.ssid, authmode=network.AUTH_OPEN)

        while self.ap.active() == False:
            self.ap.active(True)
            time.sleep(1.0)

        # setup DNSServer
        if self.dns_server is None:
            self.dns_server = dns_server.DNSServer(self.poller, self.ip)

        # setup HTTPServer
        if self.http_server is None:
            self.http_server = http_server.HTTPServer(self.poller, self.ip, callback)

    def loop(self) -> None:
        for response in self.poller.ipoll(100):
            sock, event, *others = response
            is_handled = self.handle_dns(sock, event, others)
            if not is_handled:
                self.handle_http(sock, event, others)

    def handle_dns(self, sock, event, others):
        if sock == self.dns_server.sock:
            # ignore UDB socket hangups
            if event == select.POLLHUP:
                return True
            self.dns_server.handle(sock, event, others)
            return True
        return False

    def handle_http(self, sock, event, others):
        self.http_server.handle(sock, event, others)

    def cleanup(self):
        if self.dns_server:
            self.dns_server.stop(self.poller)
        if self.http_server:
            self.http_server.stop(self.poller)
