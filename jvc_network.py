#!/usr/bin/env python3

"""JVC projector network connection module"""

import json
import select
import socket
import dumpdata

DEFAULT_PORT = 20554

class Error(Exception):
    """Error"""
    pass

class Closed(Exception):
    """Connection Closed"""
    pass

class Timeout(Exception):
    """Command Timout"""
    pass

class JVCNetwork:
    """JVC projector network connection"""
    def __init__(self, host, print_all=False, print_recv=False, print_send=False):
        self.print_recv = print_recv or print_all
        self.print_send = print_send or print_all
        self.socket = None
        self.host_port = None
        self.host = host    

    def connect(self):
        """Open network connection to projector and perform handshake"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if self.print_send:
                print('    - connecting...')
            self.socket.connect(self.host_port)
            if self.print_send:
                print('    - connected')
        except Exception as err:
            raise Error('Connection failed', err)
        self.expect(b'PJ_OK')
        self.send(b'PJREQ')
        self.expect(b'PJACK')

    def __enter__(self):        
        while True:
            if not self.host:
                print('\nError: The host address has not been set\n')                     
            try:
                self.host_port = (self.host, DEFAULT_PORT)
                self.connect()
            except Exception as err:
                print('Failed to connect to {}:{}'.format(self.host, DEFAULT_PORT))
                if isinstance(err, Error):
                    print(err.args[1])
                else:
                    print(err)
               
                raise err
            break

        return self

    def close(self):
        """Close socket"""
        if self.print_send:
            print('    - close socket')
        self.socket.close()

    def __exit__(self, exception, value, traceback):
        self.close()

    def reconnect(self):
        """Re-open network connection"""
        self.close()
        self.connect()

    def send(self, data):
        """Send data with optional data dump"""
        if self.print_send:
            dumpdata.dumpdata('    > Send:    ', '{:02x}', data)
        try:
            self.socket.send(data)
        except ConnectionAbortedError as err:
            raise Closed(err)

    def recv(self, limit=1024, timeout=0):
        """Receive data with optional timeout and data dump"""
        if timeout:
            ready = select.select([self.socket], [], [], timeout)
            if not ready[0]:
                raise Timeout('{} second timeout expired'.format(timeout))
        data = self.socket.recv(limit)
        if not len(data):
            raise Closed('Connection closed by projector')
        if self.print_recv:
            dumpdata.dumpdata('    < Received:', '{:02x}', data)
        return data

    def expect(self, res, timeout=1):
        """Receive data and compare it against expected data"""
        data = self.recv(len(res), timeout)
        if data != res:
            raise Error('Expected', res)

if __name__ == "__main__":
    print('test jvc ip connect')
    try:
        with JVCNetwork(print_recv=True, print_send=True) as jvc:
            pass
    except Error as err:
        print('Error', err)
