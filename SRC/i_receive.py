import filecmp  # file comparing library
import os  # cross-platform operating system library
import shutil  # high level file managing library
import tempfile  # for making temporary files


class Receiver:
    """
    Receiver class holding all commands receiving functions and logic
    """

    def __init__(self, _socket, _gui, _repo_path, lock):
        self._socket = _socket
        self._gui = _gui
        self._repo_path = _repo_path
        self._lock = lock
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
        self._gui.enter_text("A sync request received !")
        self._lock.acquire()
        path = (self._repo_path + self._socket.recv_msg()).replace("\\", "/")
        self.sync(path)
        self._lock.release()

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
        src = (self._repo_path + self._socket.recv_msg()).replace('\\', '/')

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
        path = (self._repo_path + self._socket.recv_msg()).replace('\\', '/')  # receives path

        fd, temp = tempfile.mkstemp()  # makes a temporary file
        self._socket.recv_file(fd)  # saves in that temporary file the data received

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
        src = (self._repo_path + self._socket.recv_msg()).replace('\\', '/')

        if os.path.exists(src):
            os.remove(src)

    def delete_dir(self):
        """
        delete directory
        """
        # adds repo path to the relative path of directory replacing
        # \ in windows operating systems to / in unix systems
        src = (self._repo_path + self._socket.recv_msg()).replace('\\', '/')

        if os.path.exists(src):
            shutil.rmtree(src)

    def mov(self):
        """
        move file from source to destination 
        """
        # adds repo path to the relative path replacing
        # \ in windows operating systems to / in unix systems
        src = (self._repo_path + self._socket.recv_msg()).replace('\\', '/')
        dst = (self._repo_path + self._socket.recv_msg()).replace('\\', '/')

        if os.path.exists(src):
            shutil.move(src, dst)  # if file exists move it
        else:

            # else request the file

            self._lock.acquire()  # make sure it is the only thread sending

            self._socket.send_msg("req")
            self._socket.send_msg(dst[len(self._repo_path):])

            self._lock.release()  # letting other threads send as well

    def respond(self):
        """
        Respond to request by sending file if still exists
        """

        # adds repo path to the relative path replacing
        # \ in windows operating systems to / in unix systems
        self._gui.enter_text("A File request received !")
        self._lock.acquire()
        src = (self._repo_path + self._socket.recv_msg()).replace('\\', '/')
        self.send(src)
        self._lock.release()

    def send(self, src):
        """
        Sends a file or a directory from its source path
        :param src: the path of file or directory to send
        :return: True if directory | False if file |  None if does not exist
        """
        directory = None
        self._gui.enter_text("Sending : {}".format(src))

        if os.path.isfile(src):
            self._socket.send_msg("cfile")
            self._socket.send_msg(src[len(self._repo_path):])
            self._socket.send_file(src)
            directory = False
        elif os.path.exists(src):
            self._socket.send_msg("cdir")
            self._socket.send_msg(src[len(self._repo_path):])
            directory = True
        self._gui.enter_text("Sending Successful.")
        return directory

    def end(self):
        """
        Ends the script
        """
        self._socket.end()  # terminates socket
        print("Terminator signal has been received !")
        exit(0)  # kills the process

    def ender(self):
        self._lock.acquire()  # make sure it is the only sending
        if self._socket.is_connected():  # if the socket is connected
            self._socket.send_msg("end")  # tell the other pair to end
        self._socket.end()  # terminate socket
        exit(0)  # kill process

    def main_loop(self):
        """
        The main loop for receiver
        """
        while True:
            self._map_func[self._socket.recv_msg()]()  # maps received command to it's function
