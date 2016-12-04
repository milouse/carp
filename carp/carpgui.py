#!/usr/bin/env python3

import os
import signal
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from carp.stash_manager import StashManager, CarpNotAStashError, \
    CarpMountError, CarpNoRemoteError, CarpNotEmptyDirectoryError
from xdg.BaseDirectory import xdg_config_home

import gi
gi.require_version('Gtk', '3.0')  # noqa: E402
gi.require_version("Notify", "0.7")  # noqa: E402
from gi.repository import Gtk, GLib, Notify


class CarpGui:
    def __init__(self):
        self.parse_args()
        self.sm = StashManager(self.config_file)
        Notify.init("Carp")

        self.tray = Gtk.StatusIcon()
        self.tray.set_from_icon_name("folder_locked")
        self.tray.set_tooltip_text("Carp")
        self.tray.connect("popup-menu", self.display_menu)

    def parse_args(self):
        parser = ArgumentParser(
            description="EncFS GUI managing tool",
            formatter_class=RawDescriptionHelpFormatter)
        parser.add_argument("-c", "--config",
                            help="Customized config file.")
        args = parser.parse_args()

        self.config_file = os.path.join(xdg_config_home, ".carp", "carp.conf")
        if args.config:
            self.config_file = os.path.expanduser(args.config)

    def display_menu(self, icon, event_button, event_time):
        menu = Gtk.Menu()

        try:
            self.sm.reload_stashes()
            mounted_stashes = self.sm.mounted_stashes()
            unmounted_stashes = self.sm.unmounted_stashes()
        except (FileNotFoundError, NotADirectoryError):
            mounted_stashes = []
            unmounted_stashes = []
            self.notify("An error occured while retrieving your "
                        "stashes' list", Notify.Urgency.CRITICAL)

        mounted_menu = Gtk.Menu()
        for st in mounted_stashes:
            mi_button = Gtk.MenuItem.new_with_label(
                "Unmount {0}".format(st))
            mi_button.connect("activate", self.encfs_action,
                              "unmount", st)
            mounted_menu.append(mi_button)

            mounted_button = Gtk.MenuItem.new_with_label(
                "Mounted stashes")
            mounted_button.set_submenu(mounted_menu)
            menu.append(mounted_button)

        unmounted_menu = Gtk.Menu()
        for st in unmounted_stashes:
            mi_button = Gtk.MenuItem.new_with_label(
                "Mount {0}".format(st))
            mi_button.connect("activate", self.encfs_action,
                              "mount", st)
            unmounted_menu.append(mi_button)

        unmounted_button = Gtk.MenuItem.new_with_label(
            "Unounted stashes")
        unmounted_button.set_submenu(unmounted_menu)
        menu.append(unmounted_button)

        sep = Gtk.SeparatorMenuItem()
        menu.append(sep)

        # add quit item
        quit_button = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_QUIT)
        quit_button.connect("activate", self.kthxbye)
        menu.append(quit_button)

        menu.show_all()
        menu.popup(None, None, Gtk.StatusIcon.position_menu,
                   self.tray, event_button, event_time)

    def encfs_action(self, widget, action, stash_name):
        if action not in ["mount", "unmount"]:
            return False

        try:
            success = getattr(self.sm, action)({"stash": stash_name})
        except (CarpMountError, CarpNotEmptyDirectoryError,
                CarpNotAStashError):
            success = False

        if success:
            verb = "mounted"
            if action == "unmount":
                verb = "unmounted"
            self.notify("{} correctly {}".format(stash_name, verb))

        else:
            verb = "mounting"
            if action == "unmount":
                verb = "unmounting"
            self.notify("An error occured while {} {}"
                        .format(verb, stash_name),
                        Notify.Urgency.CRITICAL)

    def notify(self, msg, urgency=Notify.Urgency.NORMAL):
        nota = Notify.Notification.new("Carp", msg)
        nota.set_urgency(urgency)
        nota.show()

    def kthxbye(self, widget, data=None):
        Gtk.main_quit()


if __name__ == "__main__":

    # Install signal handlers
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM,
                         Gtk.main_quit, None)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT,
                         Gtk.main_quit, None)

    CarpGui()
    Gtk.main()
