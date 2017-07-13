"""
Network Repository Version Control

Test project

"""
try:
    import watchdog
except ImportError:
    import pip

    pip.main(["install", "--user", "watchdog"])
import filecmp  # file comparing library
import os  # cross-platform operating system library
import shutil  # high level file managing library
import socket as raw_socket  # networking socket
import threading  # threads managing library
import time  # time library for adding delays
import tkinter  # GUI library
import tkinter.scrolledtext
from tkinter import filedialog, simpledialog

from watchdog.events import *  # file watcher events
from watchdog.observers import Observer  # file watcher

Lock = threading.Lock()  # a lock for thread managing

end = False


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
        self.ping = 0

    def is_connected(self):
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
        self._other_socket.send('{}\n'.format(msg).encode())  # encode a string with "new line" terminator

    def send_file(self, path):
        """
        :param path: path of the file to send 
        """
        self._other_socket.sendfile(open(path, 'rb'))  # sends the file
        time.sleep(0.5)  # delays for a while to avoid conflicts with other messages sent from socket

    def recv_file(self, path):
        """
        receive file
        stores it in a path
        
        :param path: path to save file in
        """
        file = open(path, 'wb')  # open the file
        self._other_socket.settimeout(self.ping + 0.01)  # sets socket timeout for receiving file data
        try:  # expecting a time out
            while True:
                data = self._other_socket.recv(1024)  # receives a kilobyte by kilobyte
                file.write(data)  # writes data to the opened file
        except raw_socket.timeout:
            file.close()  # closes the file
        self._other_socket.settimeout(None)  # returns time out to its default

    def recv_msg(self):
        """
        Receives a message ending with a new line terminator
        :return: received message 
        """
        data = ""  # message string
        while True:
            byte = self._other_socket.recv(1).decode()  # decode the byte received
            if byte == "\n":  # if we reached message terminator
                return data  # return received message
            data += byte


class SenderEventHandler(FileSystemEventHandler):
    """
    Sub class of EventHandler overriding methods of events and sending commands to the socket
    """

    def __init__(self, _socket, gui):
        """
        :param _socket: socket to connect to 
        """
        self.socket = _socket
        self.gui = gui
        self._method_map = {  # maps type of event to its function
            EVENT_TYPE_MODIFIED: self.on_modified,
            EVENT_TYPE_MOVED: self.on_moved,
            EVENT_TYPE_CREATED: self.on_created,
            EVENT_TYPE_DELETED: self.on_deleted,
        }

    def dispatch(self, event):
        """
        Classify events and send them to corresponding methods
        :param event: event received
        """
        Lock.acquire()  # make sure it is the only thread sending

        self.on_any_event(event)
        event_type = event.event_type
        self._method_map[event_type](event)

        Lock.release()

    def on_created(self, event):
        """
        executed when anything is created
        """
        if os.path.exists(event.src_path):  # if the file still exists
            if event.is_directory:  # if folder
                self.socket.send_msg("cdir")  # folder create command
                self.socket.send_msg(event.src_path[len(repo_path):])  # path to create
            else:  # if a file
                self.socket.send_msg("cfile")  # file create command
                self.socket.send_msg(event.src_path[len(repo_path):])  # path of that file
                self.socket.send_file(event.src_path)  # send the file

    def on_modified(self, event):
        """
        executed when anything is modified
        """
        if not event.is_directory:
            self.on_created(event)

    def on_deleted(self, event):
        """
        executed when anything is deleted
        """
        if event.is_directory:
            self.socket.send_msg('ddir')
        else:
            self.socket.send_msg('dfile')
        self.socket.send_msg(event.src_path[len(repo_path):])

    def on_moved(self, event):
        """
        executed when anything is moved
        """
        self.socket.send_msg("mov")
        self.socket.send_msg(event.src_path[len(repo_path):])
        self.socket.send_msg(event.dest_path[len(repo_path):])

    def on_any_event(self, event):
        """
        executed on any event 
        """

        self.gui.enter_text(event)


class Receiver:
    """
    Receiver class holding all commands receiving functions and logic
    """

    def __init__(self, _socket):
        self.current_time = 0
        self._socket = _socket
        self._map_func = {"cdir": self.created_dir,
                          "cfile": self.created_file,
                          "ddir": self.delete_dir,
                          "dfile": self.delete_file,
                          "mov": self.mov,
                          "end": self.end,
                          "req": self.respond,
                          "pingbk": self.ping,
                          "ping": self.ping_respond}

    def created_dir(self):
        """
        creates directory
        """
        src = (repo_path + self._socket.recv_msg()).replace('\\', '/')

        os.makedirs(src, exist_ok=True)

    def created_file(self):
        """
        makes a directory for temp file 
        receives file and stores it in temp
        if the file exists in the repo 
            if the file is the same with the received 
                delete the received
        if the file don't exist
            move the received to the repo
        """
        path = (repo_path + self._socket.recv_msg()).replace('\\', '/')

        os.makedirs('temp/', exist_ok=True)  # make a temp folder
        temp = 'temp/{}'.format(os.path.basename(path))  # name of to be saved file in temp folder
        self._socket.recv_file(temp)

        if os.path.exists(path):  # if the file exists
            if filecmp.cmp(temp, path):  # compare it
                os.remove(temp)  # if equal remove the temp and exit
                return
        else:  # if the file doesnt exist
            # make the directory of the file if don't exist
            os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.move(temp, path)  # finally move the file to its destination

    def delete_file(self):
        """
        delete file 
        """
        src = (repo_path + self._socket.recv_msg()).replace('\\', '/')

        if os.path.exists(src):
            os.remove(src)

    def delete_dir(self):
        """
        delete directory
        """
        src = (repo_path + self._socket.recv_msg()).replace('\\', '/')

        if os.path.exists(src):
            shutil.rmtree(src)

    def mov(self):
        """
        move file from source to destination 
        """
        src = (repo_path + self._socket.recv_msg()).replace('\\', '/')
        dst = (repo_path + self._socket.recv_msg()).replace('\\', '/')

        if os.path.exists(src):
            shutil.move(src, dst)  # if file exists move it
        else:

            # else request the file

            Lock.acquire()

            self._socket.send_msg("req")
            self._socket.send_msg(dst[len(repo_path):])

            Lock.release()

    def respond(self):
        """
        Respond to request by sending file if still exists
        """
        Lock.acquire()

        src = (repo_path + self._socket.recv_msg()).replace('\\', '/')

        if os.path.isfile(src):
            self._socket.send_msg("cfile")
            self._socket.send_msg(src[len(repo_path):])
            self._socket.send_file(src)
        elif os.path.exists(src):
            self._socket.send_msg("cdir")
            self._socket.send_msg(src[len(repo_path):])

        Lock.release()

    def end(self):
        """
        Ends the script
        """
        self._socket.end()
        print("Terminator signal has been received !")
        os._exit(0)

    def ender(self):
        Lock.acquire()
        if self._socket.is_connected():
            self._socket.send_msg("end")
        self._socket.end()
        os._exit(0)

    def strt_ping(self):
        self.current_time = time.time()
        Lock.acquire()
        self._socket.send_msg("pingbk")
        Lock.release()

    def ping(self):
        Lock.acquire()
        self._socket.send_msg("ping")
        Lock.release()

    def ping_respond(self):
        self._socket.ping = (time.time() - self.current_time)

    def pinger(self):
        while not end:
            self.strt_ping()
            time.sleep(10)

    def main_loop(self):
        """
        The main loop for receiver
        """
        pingos = threading.Thread(target=self.pinger)
        pingos.start()
        try:
            while not end:
                self._map_func[self._socket.recv_msg()]()
        except KeyboardInterrupt:
            self.ender()


class LogicGUI:
    def __init__(self):

        self._broad = raw_socket.socket(raw_socket.AF_INET, raw_socket.SOCK_DGRAM)
        self._broad.bind(("", 0))

        self._socket = Socket("", 0)

        self.gui = tkinter.Tk()
        self.gui.title("NRVC")

        self.gui.resizable(False, False)

        self.text = tkinter.scrolledtext.ScrolledText()
        self.text.pack()

        self.text.tag_configure('big', font=('Verdana', 12, 'bold'))
        self.text.tag_configure("small", font=('Tempus Sans ITC', 8, 'bold'))

        welcome = \
            """Network Repository Version Control\n"""
        self.text.insert(tkinter.END, welcome, "big")
        self.text.config(state=tkinter.DISABLED)

        self.b1 = tkinter.Button(text="Connect", command=self.to_connect)
        self.b2 = tkinter.Button(text="Accept Connection", command=self.accept)
        self.b1.pack()
        self.b2.pack()

        self.gui.withdraw()

        global repo_path
        repo_path = filedialog.askdirectory(title="Folder to watch")
        if not repo_path:
            exit()

        self.gui.deiconify()

        self.enter_text("Watching : {}".format(repo_path))
        self.observer = Observer()
        self.sender = SenderEventHandler(self._socket, self)
        self.receiver = Receiver(self._socket)

        self.gui.mainloop()
        self.receiver.ender()

    def start(self):
        self.enter_text("Connection Successful !")

        self.enter_text("Observer Starting !")

        self.observer.schedule(self.sender, repo_path, recursive=True)
        self.observer.start()

        self.enter_text("Receiver Starting !")

        self.receiver.main_loop()

    def to_connect(self):
        threading.Thread(target=self.connect()).start()

    def connect(self):

        self.b1.destroy()
        self.b2.destroy()
        port = ""

        while not port.isnumeric():
            port = simpledialog.askstring("NRVC", "Enter the key from the other script ")
            if not port:
                exit()

        port = int(port)

        self._broad.setsockopt(raw_socket.SOL_SOCKET, raw_socket.SO_BROADCAST, 1)

        msg = "NRVC{}".format(self._socket.port).encode()

        accepting = threading.Thread(target=self._socket.accept)
        accepting.start()
        self.enter_text('Waiting for a connection !')
        while accepting.is_alive():
            self._broad.sendto(msg, ('<broadcast>', port))
            time.sleep(0.2)
        cont = threading.Thread(target=self.start)
        cont.start()

    def accept(self):
        self.b1.destroy()
        self.b2.destroy()
        self.enter_text("Enter this key in the other script : {}".format(self._broad.getsockname()[1]))
        cont = threading.Thread(target=self.receive)
        cont.start()

    def receive(self):
        while True:
            data, addr = self._broad.recvfrom(10)
            data = data.decode()
            if data[:4] == "NRVC":
                port = int(data[4:])
                self._socket.connect(addr[0], port)
                self.start()

    def enter_text(self, msg):
        self.text.config(state=tkinter.NORMAL)
        self.text.insert(tkinter.END, "... {} \n".format(msg), "small")
        self.text.config(state=tkinter.DISABLED)


repo_path = ""

start = LogicGUI()
