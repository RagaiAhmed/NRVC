import os  # cross-platform operating system library

try:
    import watchdog  # try to import watchdogs
except ImportError:  # if not existed install it
    import pip

    pip.main(["install", "--user", "watchdog"])

from watchdog.events import *  # file watcher events


class SenderEventHandler(FileSystemEventHandler):
    """
    Sub class of EventHandler overriding methods of events and sending commands to the socket
    """

    def __init__(self, _socket, gui, lock, repo_path):
        """
        :param _socket: socket to connect to 
        :param gui: gui controller of class LogicGUI 
        """
        self.lock = lock
        self.repo_path = repo_path
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
        self.lock.acquire()  # make sure it is the only thread sending

        self.on_any_event(event)
        event_type = event.event_type
        self._method_map[event_type](event)

        self.lock.release()  # letting other threads send as well

    def on_created(self, event):
        """
        executed when anything is created
        """
        if os.path.exists(event.src_path):  # if the file still exists
            if event.is_directory:  # if folder
                self._socket.send_msg("cdir")  # folder create command
                self._socket.send_msg(event.src_path[len(self.repo_path):])  # path to create
            else:  # if a file
                self._socket.send_msg("cfile")  # file create command
                self._socket.send_msg(event.src_path[len(self.repo_path):])  # path of that file
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
        self._socket.send_msg(event.src_path[len(self.repo_path):])

    def on_moved(self, event):
        """
        executed when anything is moved
        """
        self._socket.send_msg("mov")
        self._socket.send_msg(event.src_path[len(self.repo_path):])
        self._socket.send_msg(event.dest_path[len(self.repo_path):])

    def on_any_event(self, event):
        """
        executed on any event 
        """

        self._gui.enter_text(event)
