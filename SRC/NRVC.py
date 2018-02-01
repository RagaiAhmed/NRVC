"""
Network Repository Version Control

Test project

"""
from i_gui_logic import *

GUI = LogicGUI()

try:
    GUI.mainloop()
except KeyboardInterrupt:
    GUI.end()
