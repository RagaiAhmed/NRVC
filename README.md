# Network Repository Version Control

  It is a script that run on two machines on the
  same network that is supposed to handle changes
  in the folder you choose to watch and apply it
  to the other machine in a _Master-Master_ communication
  where whenever you change anything in either of the machine
  will be applied to the other .


  ***Note it doesnt handle conflicts yet**

## How NRVC works?
  * It uses [a directory watcher]( https://github.com/gorakhargosh/watchdog)
  library to make a watcher assigned to the folder you need
  to observe for changes.
  * By sending packets over network, it make sure that these changes are
  translated as commands and sent to the other machine.
  * In addition to sending and receiving files that are changed.

## What makes it so special ?
It may help you in situations where you have two machines
and want to sync them up with the same project you working on.

## Usage :
just run the python script where a simple GUI will appear helping you
to choose the directory and starting up the connection.




