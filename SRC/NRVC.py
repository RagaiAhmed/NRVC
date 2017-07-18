"""
Network Repository Version Control

Test project

"""
try:
    import watchdog  # try to import watchdogs
except ImportError:  # if not existed install it
    import pip

    pip.main(["install", "--user", "watchdog"])

import filecmp  # file comparing library
import os  # cross-platform operating system library
import shutil  # high level file managing library
import socket as raw_socket  # networking socket
import threading  # threads managing library
import time  # time library for adding delays
# GUI library
import tkinter
import tkinter.scrolledtext
from tkinter import filedialog, simpledialog

import tempfile  # library for making temporary files

from watchdog.events import *  # file watcher events
from watchdog.observers import Observer  # file watcher

Lock = threading.Lock()  # a lock for thread managing


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
        self._other_socket.send('{}\n'.format(msg).encode())  # encode a string with "new line" at the end

    def send_file(self, path):
        """
        :param path: path of the file to send 
        """
        self._other_socket.sendfile(open(path, 'rb'))  # sends the file

    def recv_file(self, path, size):
        """
        receive file
        stores it in a path

        :param path: path to save file in
        :param size: size of file in bytes
        """
        file = open(path, 'wb')  # open the file

        while size:
            data = self._other_socket.recv(size)  # receives in a maximum buffer of size
            size -= len(data)  # decrease the buffer with the amount of data already received
            file.write(data)  # writes received data to the opened file

        file.close()  # closes the file

    def recv_msg(self):
        """
        Receives a message ending with a new line 
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
        :param gui: gui controller of class LogicGUI 
        """
        self._socket = _socket
        self._gui = gui
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

        Lock.release()  # letting other threads send as well

    def on_created(self, event):
        """
        executed when anything is created
        """
        if os.path.exists(event.src_path):  # if the file still exists
            if event.is_directory:  # if folder
                self._socket.send_msg("cdir")  # folder create command
                self._socket.send_msg(event.src_path[len(repo_path):])  # path to create
            else:  # if a file
                self._socket.send_msg("cfile")  # file create command
                self._socket.send_msg(event.src_path[len(repo_path):])  # path of that file
                self._socket.send_msg(str(os.path.getsize(event.src_path)))  # size of file
                self._socket.send_file(event.src_path)  # send the file

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
            self._socket.send_msg('ddir')
        else:
            self._socket.send_msg('dfile')
        self._socket.send_msg(event.src_path[len(repo_path):])

    def on_moved(self, event):
        """
        executed when anything is moved
        """
        self._socket.send_msg("mov")
        self._socket.send_msg(event.src_path[len(repo_path):])
        self._socket.send_msg(event.dest_path[len(repo_path):])

    def on_any_event(self, event):
        """
        executed on any event 
        """

        self._gui.enter_text(event)


class Receiver:
    """
    Receiver class holding all commands receiving functions and logic
    """

    def __init__(self, _socket):
        self._socket = _socket
        self._map_func = {"cdir": self.created_dir,
                          "cfile": self.created_file,
                          "ddir": self.delete_dir,
                          "dfile": self.delete_file,
                          "mov": self.mov,
                          "end": self.end,
                          "req": self.respond,
                          "sync": self.pre_sync}

    def pre_sync(self):
        """
        Called once at the start of the sync and receives the path to sync
        """
        # takes path and replaces \ in windows systems to / in unix systems
        path = (repo_path + self._socket.recv_msg()).replace("\\", "/")
        self.sync(path)

    def sync(self, path):
        """
        Gets every file and directory in path and sends it back 
        and if a directory gets all things inside it as well in a recurring process
        :param path: path to fetch and send
        """
        for i in os.listdir(path):
            src = os.path.join(path, i)
            if self.send(src):
                self.sync(src)

    def created_dir(self):
        """
        creates directory
        """
        # adds repo path to the relative path of directory replacing
        # \ in windows operating systems to / in unix systems
        src = (repo_path + self._socket.recv_msg()).replace('\\', '/')

        os.makedirs(src, exist_ok=True)

    def created_file(self):
        """
        makes a temp file 
        receives file and stores it in temp
        if the file exists in the repo 
            if the file is the same with the received 
                delete the received
        if the file don't exist
            move the received to the repo
        """
        path = (repo_path + self._socket.recv_msg()).replace('\\', '/')  # receives path
        size = int(self._socket.recv_msg())  # and takes size of file

        fd, temp = tempfile.mkstemp()  # makes a temporary file
        self._socket.recv_file(fd, size)  # saves in that temporary file the data received

        if os.path.exists(path):  # if the file exists in repo
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
        # adds repo path to the relative path of file replacing
        # \ in windows operating systems to / in unix systems
        src = (repo_path + self._socket.recv_msg()).replace('\\', '/')

        if os.path.exists(src):
            os.remove(src)

    def delete_dir(self):
        """
        delete directory
        """
        # adds repo path to the relative path of directory replacing
        # \ in windows operating systems to / in unix systems
        src = (repo_path + self._socket.recv_msg()).replace('\\', '/')

        if os.path.exists(src):
            shutil.rmtree(src)

    def mov(self):
        """
        move file from source to destination 
        """
        # adds repo path to the relative path replacing
        # \ in windows operating systems to / in unix systems
        src = (repo_path + self._socket.recv_msg()).replace('\\', '/')
        dst = (repo_path + self._socket.recv_msg()).replace('\\', '/')

        if os.path.exists(src):
            shutil.move(src, dst)  # if file exists move it
        else:

            # else request the file

            Lock.acquire()  # make sure it is the only thread sending

            self._socket.send_msg("req")
            self._socket.send_msg(dst[len(repo_path):])

            Lock.release()  # letting other threads send as well

    def respond(self):
        """
        Respond to request by sending file if still exists
        """

        # adds repo path to the relative path replacing
        # \ in windows operating systems to / in unix systems
        src = (repo_path + self._socket.recv_msg()).replace('\\', '/')
        self.send(src)

    def send(self, src):
        """
        Sends a file or a directory from its source path
        :param src: the path of file or directory to send
        :return: True if directory | False if file |  None if does not exist
        """
        directory = None

        Lock.acquire()  # make sure it is the only thread sending

        if os.path.isfile(src):
            self._socket.send_msg("cfile")
            self._socket.send_msg(src[len(repo_path):])
            self._socket.send_msg(os.path.getsize(src))
            self._socket.send_file(src)
            directory = False
        elif os.path.exists(src):
            self._socket.send_msg("cdir")
            self._socket.send_msg(src[len(repo_path):])
            directory = True

        Lock.release()  # letting other threads send as well

        return directory

    def end(self):
        """
        Ends the script
        """
        self._socket.end()  # terminates socket
        print("Terminator signal has been received !")
        os._exit(0)  # kills the process

    def ender(self):
        Lock.acquire()  # make sure it is the only sending
        if self._socket.is_connected():  # if the socket is connected
            self._socket.send_msg("end")  # tell the other pair to end
        self._socket.end()  # terminate socket
        os._exit(0)  # kill process

    def main_loop(self):
        """
        The main loop for receiver
        """
        try:
            while True:
                self._map_func[self._socket.recv_msg()]()  # maps received command to it's function
        except KeyboardInterrupt:
            self.ender()


class LogicGUI:
    """
    A full completed logic handles all previous classes and interaction with the user
    """

    def __init__(self):

        #  makes a broadcasting socket for discovery and connection purposes
        self._broad = raw_socket.socket(raw_socket.AF_INET, raw_socket.SOCK_DGRAM)
        self._broad.bind(("", 0))  # binds it with the current host and any available port

        self._socket = Socket("", 0)  # makes a socket for data transfere

        self.gui = tkinter.Tk()  # GUI window
        self.gui.title("NRVC")

        self.gui.resizable(False, False)

        self.text = tkinter.scrolledtext.ScrolledText()  # a scrollable text box
        self.text.pack()

        self.text.tag_configure('big', font=('Verdana', 12, 'bold'))
        self.text.tag_configure("small", font=('Tempus Sans ITC', 8, 'bold'))

        welcome = \
            """Network Repository Version Control\n"""
        self.text.insert(tkinter.END, welcome, "big")
        self.text.config(state=tkinter.DISABLED)  # disabled means READONLY

        self.b1 = tkinter.Button(text="Connect", command=self.connect)
        self.b2 = tkinter.Button(text="Accept Connection", command=self.accept)
        self.b1.pack()
        self.b2.pack()

        self.gui.withdraw()  # just hides the main window

        global repo_path
        repo_path = filedialog.askdirectory(title="Folder To Watch")  # asks for directory to watch
        if not repo_path:  # if he closed the window exit
            exit()

        self.gui.deiconify()  # un hide main window

        self.enter_text("Watching : {}".format(repo_path))  # tells you what directory you are watching

        self.observer = Observer()  # declares observer
        self.sender = SenderEventHandler(self._socket, self)  # declares sender
        self.receiver = Receiver(self._socket)  # declares receiver

        self.gui.mainloop()  # enter the window mainloop
        self.receiver.ender()  # if the mainloop exited end the script

    def start(self):
        """
        Starting the observer, sender and receiver and such
        """
        self.enter_text("Connection Successful !")

        tkinter.Button(text="Sync", command=self.sync_req).pack()  # makes a sync button

        self.enter_text("Observer Starting !")

        self.observer.schedule(self.sender, repo_path, recursive=True)
        self.observer.start()  # starts a new thread observing repo path

        self.enter_text("Receiver Starting !")

        self.receiver.main_loop()  # enters the receiver main loop

    def connect(self):
        """
        in case of connecting the function handles connecting to another script
        """
        # destroy the choosing buttons
        self.b1.destroy()
        self.b2.destroy()

        # gets port of the broadcast listening socket of the other script to send to
        port = ""
        while not port.isnumeric():
            port = simpledialog.askstring("NRVC", "Enter the key from the other script ")
            if not port:
                exit()

        port = int(port)

        self._broad.setsockopt(raw_socket.SOL_SOCKET, raw_socket.SO_BROADCAST, 1)  # getting socket ready for sending

        # a Hello message holding the main socket port number totally hidden from user
        msg = "NRVC{}".format(self._socket.port).encode()

        # thread handling receiving connections
        accepting = threading.Thread(target=self._socket.accept)
        accepting.start()
        self.enter_text('Trying To Connect !')
        while accepting.is_alive():  # since there is no connections continue broadcasting
            self._broad.sendto(msg, ('<broadcast>', port))
            time.sleep(0.2)  # in a specific interval
        cont = threading.Thread(target=self.start)
        cont.start()

    def accept(self):
        """
        Receives broadcast message on a specific port 
        and gets information to connect to the other script 
        """
        # destroy choose buttons
        self.b1.destroy()
        self.b2.destroy()
        # shows the port of the broadcasting socket as a key to get a broadcast message to
        self.enter_text("Enter this key in the other script : {}".format(self._broad.getsockname()[1]))
        # a new thread for handling the receiving  , leaving the mainloop thread to continue handling gui
        cont = threading.Thread(target=self.receive)
        cont.start()

    def receive(self):
        """
            Receives broadcast messages on a specific port
        """
        while True:
            data, addr = self._broad.recvfrom(10)  # receives 10 bytes from an address
            data = data.decode()
            if data[:4] == "NRVC":  # to avoid being interfered with other messages
                port = int(data[4:])  # the port number of the other script main socket
                self._socket.connect(addr[0], port)  # connect our socket to the other socket
                self.start()

    def enter_text(self, msg):
        """
        adds a new line of information to the visible text box for the user
        :param msg:  message to add
        """
        self.text.config(state=tkinter.NORMAL)
        self.text.insert(tkinter.END, "... {} \n".format(msg), "small")
        self.text.config(state=tkinter.DISABLED)

    def sync_req(self):
        """
        Called when you hit sync button 
        """
        path_to_sync = ""

        while not path_to_sync.startswith(repo_path):  # if the path to sync is not in the repo path
            self.enter_text("Please choose the directory inside the repo to Sync")
            path_to_sync = filedialog.askdirectory(title="Path to sync", initialdir=repo_path)
            if path_to_sync is None:
                return
        # another check step
        if simpledialog.messagebox.askquestion("NRVC", "Are you sure you want to sync this path ?\n"
                                                       "Note that any conflicts will be overwritten."):
            Lock.acquire()
            self._socket.send_msg("sync")
            self._socket.send_msg(path_to_sync[len(repo_path):])
            Lock.release()


repo_path = ""  # the supposed to be repository path

start = LogicGUI()  # start
