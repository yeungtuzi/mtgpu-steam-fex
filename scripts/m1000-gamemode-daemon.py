#!/usr/bin/env python3
"""Small session D-Bus service so the KWin shortcut can exit game mode."""
import subprocess
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from dbus.service import BusName, Object, method
from gi.repository import GLib

DBusGMainLoop(set_as_default=True)
bus = dbus.SessionBus()
name = BusName("org.m1000.GameMode", bus)


class GameMode(dbus.service.Object):
    @method("org.m1000.GameMode", in_signature="", out_signature="")
    def Stop(self):
        subprocess.run(["/opt/steamos/bin/game-mode", "stop"], check=False)

    @method("org.m1000.GameMode", in_signature="", out_signature="")
    def Start(self):
        subprocess.run(["/opt/steamos/bin/game-mode", "start"], check=False)


GameMode(bus, "/GameMode")
GLib.MainLoop().run()
