from i_socket import *
from i_receive import *
import socket as raw_socket  # networking socket
import time  # time library for adding delays
import tkinter
import tkinter.scrolledtext
from tkinter import filedialog, simpledialog
from watchdog.observers import Observer  # file watcher
import threading  # threads managing library


class LogicGUI:
    """
    A full completed logic handles all previous classes and interaction with the user
    """

    def __init__(self, ):

        self.lock = threading.Lock()  # for threading purposes

        #  makes a broadcasting socket for discovery and connection purposes
        self._broad = raw_socket.socket(raw_socket.AF_INET, raw_socket.SOCK_DGRAM)
        self._broad.bind(("", 0))  # binds it with the current host and any available port

        self._socket = Socket("", 0)  # makes a socket for data transfer

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

        self.repo_path = filedialog.askdirectory(title="Folder To Watch")  # asks for directory to watch
        if not self.repo_path:  # if he closed the window exit
            exit()

        self.gui.deiconify()  # un hide main window

        self.enter_text("Watching : {}".format(self.repo_path))  # tells you what directory you are watching

        self.observer = Observer()  # declares observer
        self.sender = SenderEventHandler(self._socket, self, self.lock, self.repo_path)  # declares sender
        self.receiver = Receiver(self._socket, self, self.repo_path, self.lock)  # declares receiver

    def mainloop(self):
        self.gui.mainloop()  # enter the window mainloop
        self.end()  # if the mainloop exited end the script

    def start(self):
        """
        Starting the observer, sender and receiver and such
        """
        self.enter_text("Connection Successful !")

        tkinter.Button(text="Sync", command=self.sync_req).pack()  # makes a sync button

        self.enter_text("Observer Starting !")

        self.observer.schedule(self.sender, self.repo_path, recursive=True)
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

        while not path_to_sync.startswith(self.repo_path):  # if the path to sync is not in the repo path
            self.enter_text("Please choose the directory inside the repo to Sync")
            path_to_sync = filedialog.askdirectory(title="Path to sync", initialdir=self.repo_path)
            if path_to_sync == "":
                return
        # another check step
        if simpledialog.messagebox.askquestion("NRVC", "Are you sure you want to sync this path ?\n"
                                                       "Note that any conflicts will be overwritten."):
            self.lock.acquire()
            self._socket.send_msg("sync")
            self._socket.send_msg(path_to_sync[len(self.repo_path):])
            self.enter_text("Sync requested !")
            self.lock.release()

    def end(self):
        self.receiver.ender()
