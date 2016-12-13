#!/usr/bin/env python3

import sys
import carp
import signal

import gi
gi.require_version('Gtk', '3.0')  # noqa: E402
from gi.repository import Gtk, GLib

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "gui":
        sys.argv.pop()
        # Install signal handlers
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM,
                             Gtk.main_quit, None)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT,
                             Gtk.main_quit, None)
        carp.CarpGui()
        Gtk.main()

    else:
        carp.CarpCli()
