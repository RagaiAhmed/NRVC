# Network Repository Version Control

*Notice this is a test project and not fully functional yet and may have more functions in the future

What is NRVC?
  It is a script that run on two machines on the same network that is supposed to handle changes in the folder you choose to watch and apply it to the other machine in a Master-Master communication where whenever you change anything in either of the machine will be applied to the other .
  *Note it doesnt handle conflicts yet

How NRVC works?
  It uses  https://github.com/gorakhargosh/watchdog library to make a watcher assigned to the folder you need to observe for changes. Using sockets and other tools it make sure that these changes are translated as commands and sent to the other machine. Where there it makes the changes as the commands it received sending and requesting files and so.
  
