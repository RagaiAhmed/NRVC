"""
Network Repository Version Control

Test project

"""
from watchdog.observers import Observer  # file watcher
from watchdog.events import *  # file watcher events
import socket as raw_socket  # networking socket
import os  # cross-platform operating system library
import filecmp  # file comparing library
import shutil  # high level file managing library
import time  # time library for adding delays
import tkinter  # GUI library
from tkinter import filedialog, messagebox, simpledialog
import threading  # threads managing library

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
        self._other_addr = None

    def accept(self):
        """
        waits for a connection
        :return: True if connected | False if already connected 
        """
        if self._other_socket:
            return False

        self._my_socket.listen()
        self._other_socket, self._other_addr = self._my_socket.accept()

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
        self._other_socket.send((msg + '\n').encode())  # encode a string with "new line" terminator

    def send_file(self, path):
        """
        :param path: path of the file to send 
        """
        self._other_socket.sendfile(open(path, 'rb'))  # sends the file
        time.sleep(0.1)  # delays for a while to avoid conflicts with other messages sent from socket

    def recv_file(self, path):
        """
        receive file
        stores it in a path
        
        :param path: path to save file in
        """
        file = open(path, 'wb')  # open the temp file
        self._other_socket.settimeout(0.01)  # sets socket timeout for receiving file data
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


class EventHandlerSender(FileSystemEventHandler):
    """
    Sub class of EventHandler overriding methods of events and sending commands to the socket
    """

    def __init__(self, _socket):
        """
        :param _socket: socket to connect to 
        """
        self.socket = _socket
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

        print(event)


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
                          "req": self.respond}

    def created_dir(self):
        """
        creates directory
        """
        src = repo_path + self._socket.recv_msg()

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
        path = repo_path + self._socket.recv_msg()

        os.makedirs(os.path.join('temp', ''), exist_ok=True)  # make a temp folder
        temp = os.path.join('temp', os.path.basename(path))  # name of to be saved file in temp folder
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
        src = repo_path + self._socket.recv_msg()

        if os.path.exists(src):
            os.remove(src)

    def delete_dir(self):
        """
        delete directory
        """
        src = repo_path + self._socket.recv_msg()

        if os.path.exists(src):
            shutil.rmtree(src)

    def mov(self):
        """
        move file from source to destination 
        """
        src = repo_path + self._socket.recv_msg()
        dst = repo_path + self._socket.recv_msg()

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

        src = repo_path + self._socket.recv_msg()

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
        exit("\tThe Other Script Ended !\n")

    def main_loop(self):
        """
        The main loop for receiver
        """
        try:
            print("Network Receiver Started !")
            while True:
                self._map_func[self._socket.recv_msg()]()
        except KeyboardInterrupt:
            socket.send_msg("end")
            self._socket.end()


window = tkinter.Tk()
window.title("NRVC")

window.geometry("{}x{}+{}+{}".format(300, 100, (window.winfo_screenwidth() - 100) // 2,
                                     (window.winfo_screenheight() - 100) // 2))
window.withdraw()

messagebox.showinfo("NRVC",
                    "Welcome to Network Repository Version Control Program.\n"
                    "\n"
                    "Please , Kindly choose the Folder you want to watch for changes.")

repo_path = filedialog.askdirectory(title="Directory to Watch", initialdir=os.environ["HOME"])
if not repo_path:
    exit()


def accept():
    window.withdraw()

    acception = threading.Thread(target=socket.accept)
    acception.start()

    messagebox.showinfo("Waiting for connection",
                        "Open the script in the other computer. \n"
                        "Enter the following in order to connect to this script.\n"
                        "\n"
                        "Host:{}\n"
                        "Port:{}\n".format(raw_socket.gethostname(), socket.port))
    acception.join()

    window.quit()
    window.destroy()


def connect():
    window.withdraw()

    host = None
    while not host:
        host = simpledialog.askstring("NRVC", "Please enter the host of the other script to connect")

        if host is None:
            exit()

    port = ""
    while not port.isnumeric():
        port = simpledialog.askstring("NRVC",
                                      "Please enter the port of the other script to connect")
        if port is None:
            exit()

    socket.connect(host, int(port))
    window.quit()
    window.destroy()


b_accept = tkinter.Button(text="Wait For Connection", command=accept)
b_accept.pack()

b_connect = tkinter.Button(text="Connect", command=connect)
b_connect.pack()

socket = Socket(raw_socket.gethostname(), 0)

window.deiconify()
window.mainloop()

obs = Observer()
ev = EventHandlerSender(socket)
obs.schedule(ev, repo_path, recursive=True)
obs.start()
print("Files Observer Started !")
Receiver(socket).main_loop()
