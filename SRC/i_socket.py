import socket as raw_socket  # networking socket
from i_watch import *


class Socket:
    """
    High level Abstraction of dealing with sockets
    Socket class holding all needed socket methods and variables
    """

    def __init__(self, current_host, current_port):
        """
        :param current_host: the ip or host name of current socket
        :param current_port: port on the device where the socket will send and receive
        """
        self._my_socket = raw_socket.socket()  # makes a socket
        self._my_socket.bind((current_host, current_port))  # binds it current host and port
        self.port = self._my_socket.getsockname()[1]  # stores port number

        self._other_socket = None  # initialize variables for other socket

    def is_connected(self):
        """
        :return: True if connected else False
        """
        return self._other_socket is not None

    def accept(self):
        """
        waits for a connection
        :return: True if connected | False if already connected 
        """
        if self._other_socket:
            return False

        self._my_socket.listen()
        self._other_socket, other_addr = self._my_socket.accept()

        return True

    def connect(self, other_host, other_port):
        """
        connects the socket to another socket
        :param other_host: host of the other socket
        :param other_port: port of the other socket
        :return: True if connected | False if was already connected
        """
        if self._other_socket:
            return False

        self._my_socket.connect((other_host, other_port))
        self._other_socket = self._my_socket

        return True

    def end(self):
        """
        Closes current socket
        """

        self._my_socket.close()

    def send_msg(self, msg):
        """
        :param msg: message to send
        """
        self._other_socket.sendall('{}\n'.format(msg).encode())  # send the message

    def send_file(self, path):
        """
        :param path: path of the file to send 
        """
        self.send_msg(str(os.path.getsize(path)))  # sends file size
        self._other_socket.sendfile(open(path, 'rb'))  # sends the file

    def recv_file(self, path):
        """
        file size
        stores it in a path

        :param path: path to save file in
        """
        size = int(self.recv_msg())  # takes size of file

        file = open(path, 'wb')  # open the file

        while size:
            data = self._other_socket.recv(size)  # receives in a maximum buffer of size
            size -= len(data)  # decrease the buffer with the amount of data already received
            file.write(data)  # writes received data to the opened file

        file.close()  # closes the file

    def recv_msg(self):
        """
        Receives a message 
        :return: received message 
        """
        msg = []  # list of bytes holding the messages

        while True:
            # store data received byte by byte as it is a short message
            data = self._other_socket.recv(1)
            if data == b"\n":
                # forms a whole binary line representing message then decoding it
                return b"".join(msg).decode()
            msg.append(data)
