try:
    import usocket as socket
except:
    import socket
try:
    import uselect as select
except:
    import select

import gc
import uio
import uerrno
from collections import namedtuple

from server import Server

WriteConn = namedtuple("WriteConn", ["body", "buff", "buffmv", "write_range"])
ReqInfo = namedtuple("ReqInfo", ["type", "path", "params", "host"])


class HTTPServer(Server):
    def __init__(self, poller, ip, callback):
        super().__init__(poller, 80, socket.SOCK_STREAM, "HTTP Server")

        if type(ip) is bytes:
            self.ip = ip
        else:
            self.ip = ip.encode()
        self.request = dict()
        self.conns = dict()

        # define routes that return files, or with a callback
        self.routes = {
            b"/": b"./index.html",
            b"/submit": callback,
        }

        # queue up to 5 connection requests before refusing
        self.sock.listen(5)
        self.sock.setblocking(False)

    def handle(self, sock, event, others):
        if sock is self.sock:
            # client connecting on port 80, so spawn off a new
            # socket to handle this connection
            self.accept(sock)
        elif event & select.POLLIN:
            # socket has data to read in
            self.read(sock)
        elif event & select.POLLOUT:
            # existing connection has space to send more data
            self.write_to(sock)

    def accept(self, server_sock):
        """accept a new client request socket and register it for polling"""

        try:
            client_sock, addr = server_sock.accept()
        except OSError as e:
            if e.args[0] == uerrno.EAGAIN:
                return

        client_sock.setblocking(False)
        client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.poller.register(client_sock, select.POLLIN)

    def read(self, sock):
        """read in client request from socket"""

        data = sock.read()
        if not data:
            # no data in the TCP stream, so close the socket
            self.close(sock)
            return

        # add new data to the full request
        sid = id(sock)
        self.request[sid] = self.request.get(sid, b"") + data

        # check if additional data expected
        if data[-4:] != b"\r\n\r\n":
            # HTTP request is not finished if no blank line at the end
            # wait for next read event on this socket instead
            return

        # get the completed request
        req = self.parse_request(self.request.pop(sid))

        if not self.is_valid_req(req):
            headers = (
                b"HTTP/1.1 307 Temporary Redirect\r\n"
                b"Location: http://{:s}/\r\n".format(self.ip)
            )
            body = uio.BytesIO(b"")
            self.prepare_write(sock, body, headers)
            return

        body, headers = self.get_response(req)

        self.prepare_write(sock, body, headers)

    def prepare_write(self, sock, body, headers):
        # add newline to headers to signify transition to body
        headers += "\r\n"
        # TCP/IP MSS is 536 bytes, so create buffer of this size and
        # initially populate with header data
        buff = bytearray(headers + "\x00" * (536 - len(headers)))
        # use memoryview to read directly into the buffer without copying
        buffmv = memoryview(buff)
        # start reading body data into the memoryview starting after
        # the headers, and writing at most the remaining space of the buffer
        # return the number of bytes written into the memoryview from the body
        bw = body.readinto(buffmv[len(headers) :], 536 - len(headers))
        # save place for next write event
        c = WriteConn(body, buff, buffmv, [0, len(headers) + bw])
        self.conns[id(sock)] = c
        # let the poller know we want to know when it's OK to write
        self.poller.modify(sock, select.POLLOUT)

    def write_to(self, sock):
        """write the next message to an open socket"""

        # get the data that needs to be written to this socket
        c = self.conns[id(sock)]
        if c:
            # write next 536 bytes (max) into the socket
            bytes_written = sock.write(c.buffmv[c.write_range[0] : c.write_range[1]])
            if not bytes_written or c.write_range[1] < 536:
                # either we wrote no bytes, or we wrote < TCP MSS of bytes
                # so we're done with this connection
                self.close(sock)
            else:
                # more to write, so read the next portion of the data into
                # the memoryview for the next send event
                self.buff_advance(c, bytes_written)

    def buff_advance(self, connection, bytes_written):
        """advance the writer buffer for this connection to next outgoing bytes"""

        if bytes_written == connection.write_range[1] - connection.write_range[0]:
            # wrote all the bytes we had buffered into the memoryview
            # set next write start on the memoryview to the beginning
            connection.write_range[0] = 0
            # set next write end on the memoryview to length of bytes
            # read in from remainder of the body, up to TCP MSS
            connection.write_range[1] = connection.body.readinto(connection.buff, 536)
        else:
            # didn't read in all the bytes that were in the memoryview
            # so just set next write start to where we ended the write
            connection.write_range[0] += bytes_written

    def parse_request(self, req):
        """parse a raw HTTP request to get items of interest"""

        req_lines = req.split(b"\r\n")
        req_type, full_path, http_ver = req_lines[0].split(b" ")
        path = full_path.split(b"?")
        base_path = path[0]
        query = path[1] if len(path) > 1 else None
        try:
            query_params = (
                {
                    key: val
                    for key, val in [param.split(b"=") for param in query.split(b"&")]
                }
                if query
                else {}
            )
        except Exception:
            query_params = {}

        host = [line.split(b": ")[1] for line in req_lines if b"Host:" in line][0]
        return ReqInfo(req_type, base_path, query_params, host)

    def get_response(self, req):
        """generate a response body and headers, given a route"""

        headers = b"HTTP/1.1 200 OK\r\n"
        route = self.routes.get(req.path, None)

        # if route points to a file, we return the content of the file
        if type(route) is bytes:
            # expect a filename, so return contents of file
            return open(route, "rb"), headers

        # if route points to a callback, we execute the callback
        if callable(route):
            response = route(req.params)
            body = response[0] or b""
            headers = response[1] or headers
            return uio.BytesIO(body), headers

        headers = b"HTTP/1.1 404 Not Found\r\n"
        return uio.BytesIO(b""), headers

    def is_valid_req(self, req):
        if req.host != self.ip:
            # force a redirect to the MCU's IP address
            return False
        # redirect if we don't have a route for the requested path
        return req.path in self.routes

    def close(self, sock):
        """close the socket, unregister from poller, and delete connection"""

        sock.close()
        self.poller.unregister(sock)
        sid = id(sock)
        if sid in self.request:
            del self.request[sid]
        if sid in self.conns:
            del self.conns[sid]
        gc.collect()
