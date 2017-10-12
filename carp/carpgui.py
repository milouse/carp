#!/usr/bin/env python3

import os
import re
import sys
import signal
import subprocess
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from carp.stash_manager import StashManager, CarpNotAStashError, \
    CarpMountError, CarpNoRemoteError, CarpNotEmptyDirectoryError, \
    CarpMustBePushedError
from carp.version import VERSION
from xdg.BaseDirectory import xdg_config_home

import gi
gi.require_version('Gtk', '3.0')  # noqa: E402
gi.require_version("Notify", "0.7")  # noqa: E402
from gi.repository import Gtk, GLib, Notify

import gettext
CARP_L10N_PATH = "./locales"
# Explicit declaration to avoid flake8 fear.
gettext.bindtextdomain("carp", CARP_L10N_PATH)
gettext.textdomain("carp")
_ = gettext.gettext

CARP_POSSIBLE_STATUS = {
    "mount": _("mount"),
    "umount": _("unmount"),
    "pull": _("pull"),
    "push": _("push")
}

CARP_POSSIBLE_INOTIFY_STATUS = {
    "created": _("created"),
    "deleted": _("deleted"),
    "modified": _("modified"),
    "moved": _("moved")
}


class CarpGui:
    def __init__(self):
        self.activity_re = re.compile("^\[([0-9\s:-]+)\] (.+) "
                                      "(created|deleted|modified|moved)$")
        self.parse_args()
        self.sm = StashManager(self.config_file)

        hide_file_pattern = "(?:^\.~.+\#|^\.\#|~$|\.lock$|~\.[A-Z0-9]{6}$)"
        if "general" in self.sm.config and \
           "hide_file_pattern" in self.sm.config["general"]:
            hide_file_pattern = self.sm.config["general"]["hide_file_pattern"]
        self.lock_re = re.compile(hide_file_pattern)

        Notify.init("Carp")

        self.must_autostart = os.path.isfile(os.path.join(
            xdg_config_home, "autostart", "carp.desktop"))

        self.tray = Gtk.StatusIcon()
        self.tray.set_from_icon_name("folder_locked")
        self.tray.set_tooltip_text("Carp")
        self.tray.connect("popup-menu", self.display_menu)

    def parse_args(self):
        carp_desc = _("EncFS GUI managing tool")
        parser = ArgumentParser(
            description=carp_desc,
            formatter_class=RawDescriptionHelpFormatter)
        parser.add_argument("-v", "--version", action="store_true",
                            help="Display carp version information"
                                 " and exit.")
        parser.add_argument("-c", "--config",
                            help=_("Customized config file."))
        args = parser.parse_args()

        if args.version:
            print("{} - v{}".format(carp_desc, VERSION))
            sys.exit(0)

        self.config_file = os.path.join(xdg_config_home, ".carp", "carp.conf")
        if args.config:
            self.config_file = os.path.expanduser(args.config)

    def build_activity_submenu(self, log_file):
        file_lines = []
        with open(log_file, "r") as f:
            file_lines = f.readlines()

        modified_files = []
        last_line = None
        for line in file_lines:
            match = self.activity_re.match(line)
            if match is None:
                continue
            concerned_file = os.path.basename(match[2])
            if self.lock_re.search(concerned_file) is not None:
                continue
            new_line = "{}{}".format(match[2], match[3])
            if new_line == last_line:
                continue
            last_line = new_line
            modified_files.append((match[1], match[2], match[3]))

        if len(modified_files) == 0:
            return None

        modified_files = modified_files[-10:]
        lfmenu = Gtk.Menu()
        for line in modified_files:
            istatus = CARP_POSSIBLE_INOTIFY_STATUS[line[2]]
            lb = Gtk.MenuItem.new_with_label(
                _("{0} ({1} at {2})").format(line[1], istatus, line[0]))
            if line[2] == 'deleted':
                lb.set_sensitive(False)
            else:
                lb.connect("activate", self.open_in_file_browser,
                           line[1], True)
            lfmenu.append(lb)

        return lfmenu

    def build_stash_submenu(self, stash_name, is_unmounted=True):
        mm = Gtk.Menu()

        current_state_info = Gtk.MenuItem.new_with_label(
            _("Use {0} of space").format(self.sm.file_space_usage(stash_name)))
        current_state_info.set_sensitive(False)
        mm.append(current_state_info)

        mount_label = _("Unmount {0}").format(stash_name)
        mount_action = "umount"
        if is_unmounted:
            mount_label = _("Mount {0}").format(stash_name)
            mount_action = "mount"
        else:
            config_dir = os.path.join(xdg_config_home, ".carp", stash_name)
            log_file = os.path.join(config_dir, "activity.log")

            lfmb = Gtk.MenuItem.new_with_label(_("Last changes"))
            lfmb.set_sensitive(False)
            if os.path.exists(log_file):
                lfmenu = self.build_activity_submenu(log_file)
                if lfmenu is not None:
                    lfmb.set_sensitive(True)
                    lfmb.set_submenu(lfmenu)

            mm.append(lfmb)

        mi_button = Gtk.MenuItem.new_with_label(mount_label)
        mi_button.connect("activate", self.encfs_action,
                          mount_action, stash_name)
        mm.append(mi_button)

        if is_unmounted and self.sm.may_sync(stash_name):
            mi_button = Gtk.MenuItem.new_with_label(
                _("Pull {0}").format(stash_name))
            mi_button.connect("activate", self.encfs_action,
                              "pull", stash_name)
            mm.append(mi_button)

            mi_button = Gtk.MenuItem.new_with_label(
                _("Push {0}").format(stash_name))
            mi_button.connect("activate", self.encfs_action,
                              "push", stash_name)
            mm.append(mi_button)
        elif not is_unmounted:
            mi_button = Gtk.MenuItem.new_with_label(_("Open"))
            mi_button.connect("activate", self.open_in_file_browser,
                              stash_name)
            mm.append(mi_button)

            mi_button = Gtk.MenuItem.new_with_label(_("Open in term"))
            mi_button.connect("activate", self.open_in_term, stash_name)
            mm.append(mi_button)

        mb = Gtk.MenuItem.new_with_label(stash_name)
        mb.set_submenu(mm)
        return mb

    def display_menu(self, icon, event_button, event_time):
        menu = Gtk.Menu()

        try:
            self.sm.reload_stashes()
            mounted_stashes = self.sm.mounted_stashes()
            unmounted_stashes = self.sm.unmounted_stashes()
        except (FileNotFoundError, NotADirectoryError):
            mounted_stashes = []
            unmounted_stashes = []
            self.notify(_("An error occured while retrieving your "
                          "stashes' list"), Notify.Urgency.CRITICAL)

        if any(mounted_stashes):
            for st in mounted_stashes:
                menu.append(self.build_stash_submenu(st, False))

            sep = Gtk.SeparatorMenuItem()
            menu.append(sep)

        for st in unmounted_stashes:
            menu.append(self.build_stash_submenu(st))

        sep = Gtk.SeparatorMenuItem()
        menu.append(sep)

        # Launch at session start
        mi_button = Gtk.CheckMenuItem(_("Automatically start"))
        mi_button.set_active(self.must_autostart)
        menu.append(mi_button)
        mi_button.connect("toggled", self.toggle_must_autostart)

        # report a bug
        reportbug = Gtk.MenuItem.new_with_label(_("Report a bug"))
        menu.append(reportbug)
        reportbug.connect("activate", self.report_a_bug)

        # show about dialog
        about = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_ABOUT)
        menu.append(about)
        about.connect("activate", self.show_about_dialog)

        # add quit item
        quit_button = Gtk.ImageMenuItem.new_from_stock(Gtk.STOCK_QUIT)
        quit_button.connect("activate", self.kthxbye)
        menu.append(quit_button)

        menu.show_all()
        menu.popup(None, None, Gtk.StatusIcon.position_menu,
                   self.tray, event_button, event_time)

    def encfs_action(self, widget, action, stash_name):
        if action not in ["mount", "umount", "pull", "push"]:
            return False

        cmd_opts = {"stash": stash_name}
        if action == "mount" and not self.sm.stashes[stash_name]["pass_file"]:
            cmd_opts["pass_cmd"] = "zenity --password"

        try:
            success = getattr(self.sm, action)(cmd_opts)
        except (CarpMountError, CarpNotEmptyDirectoryError,
                CarpNotAStashError, CarpNoRemoteError,
                CarpMustBePushedError):
            success = False

        if success:
            self.notify(_("{0} correctly {1}ed")
                        .format(stash_name, CARP_POSSIBLE_STATUS[action]))

        else:
            self.notify(_("An error occured while {1}ing {0}")
                        .format(stash_name, CARP_POSSIBLE_STATUS[action]),
                        Notify.Urgency.CRITICAL)

    def open_in_file_browser(self, widget, stash_name_or_path,
                             absolute_path=False):
        if absolute_path:
            target_folder = stash_name_or_path
        else:
            target_folder = os.path.join(self.sm.mount_point(),
                                         stash_name_or_path)
        subprocess.Popen(["gio", "open", target_folder])

    def open_in_term(self, widget, stash_name):
        target_folder = os.path.join(self.sm.mount_point(), stash_name)
        os.chdir(target_folder)
        subprocess.Popen(["st"])

    def notify(self, msg, urgency=Notify.Urgency.NORMAL):
        nota = Notify.Notification.new("Carp", msg)
        nota.set_urgency(urgency)
        nota.show()

    def toggle_must_autostart(self, widget):
        self.must_autostart = widget.get_active()
        if not os.path.isdir(os.path.join(xdg_config_home, "autostart")):
            self.must_autostart = False
            return False
        file_yet_exists = os.path.isfile(
            os.path.join(xdg_config_home, "autostart", "carp.desktop"))
        if not file_yet_exists and self.must_autostart:
            with open(os.path.join(
                    xdg_config_home, "autostart", "carp.desktop"),
                      "w") as asfile:
                asfile.write("""\
[Desktop Entry]
Name={}
GenericName={}
Comment={}
Exec=carp gui
Icon=folder_locked
Terminal=false
Type=Application
X-MATE-Autostart-enabled=true
X-GNOME-Autostart-Delay=20
StartupNotify=false
""".format(_("Carp"), _("EncFS manager"), _("EncFS GUI managing tool")))

        elif file_yet_exists and not self.must_autostart:
            os.remove(os.path.join(
                xdg_config_home, "autostart", "carp.desktop"))

    def report_a_bug(self, widget):
        subprocess.Popen(
            ["gio", "open",
             "https://projects.deparis.io/projects/carp/issues/new"])

    def show_about_dialog(self, widget):
        about_dialog = Gtk.AboutDialog()
        about_dialog.set_destroy_with_parent(True)
        about_dialog.set_icon_name("folder_locked")
        about_dialog.set_name(_("Carp"))
        about_dialog.set_website("https://projects.deparis.io/projects/carp/")
        about_dialog.set_comments(_("EncFS GUI managing tool"))
        about_dialog.set_version(VERSION)
        about_dialog.set_copyright(_("Carp is released under the WTFPL"))
        about_dialog.set_authors(["Étienne Deparis <etienne@depar.is>"])
        about_dialog.run()
        about_dialog.destroy()

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
