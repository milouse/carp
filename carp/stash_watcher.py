#!/usr/bin/env python3

import os
import sys
from datetime import datetime
from pyinotify import WatchManager, ThreadedNotifier, ProcessEvent, \
     NotifierError, IN_ATTRIB, IN_CLOSE_WRITE, IN_CREATE, IN_DELETE, \
     IN_MODIFY
from xdg.BaseDirectory import xdg_config_home

import gettext
CARP_L10N_PATH = "./locales"
# Explicit declaration to avoid flake8 fear.
gettext.bindtextdomain("carp", CARP_L10N_PATH)
gettext.textdomain("carp")
_ = gettext.gettext


class CarpStopNotifierError(Exception):
    pass


class CarpEventHandler(ProcessEvent):
    def __init__(self, stash_name):
        self.stash_name = stash_name
        self.change_file = os.path.join(
            xdg_config_home, ".carp", stash_name, "last-change")

    def process_default(self, event):
        # print("{}: {}".format(event.maskname, event.pathname))
        with open(self.change_file, "w") as f:
            f.write(str(round(datetime.now().timestamp())))


class StashWatcher:
    def __init__(self):
        self.watchers = {}

    def start(self, stash_name, stash_root):
        if stash_name in self.watchers:
            print(_("Trying to start an already started "
                    "watch for {0}").format(stash_name),
                  file=sys.stderr)
            return False

        wm = WatchManager()
        notifier = ThreadedNotifier(wm, CarpEventHandler(stash_name))

        new_watch = {
            "wm": wm,
            "wdd": {},
            "notifier": notifier
        }

        try:
            new_watch["notifier"].start()

        except NotifierError:
            print(_("Error starting watch for {0}").format(stash_name),
                  file=sys.stderr)

        watch_mask = (IN_ATTRIB | IN_CLOSE_WRITE | IN_CREATE |
                      IN_DELETE | IN_MODIFY)
        new_watch["wdd"] = new_watch["wm"].add_watch(
            stash_root, watch_mask, rec=True)

        self.watchers[stash_name] = new_watch

        watch_file = os.path.join(
            xdg_config_home, ".carp", stash_name, "watched")
        open(watch_file, "w").close()

    def stop(self, stash_name):
        if stash_name not in self.watchers:
            print(_("Trying to stop an already stopped "
                    "watch for {0}").format(stash_name),
                  file=sys.stderr)
            return False

        wdd = self.watchers[stash_name]["wdd"]
        self.watchers[stash_name]["wm"].rm_watch(wdd.values(), rec=True)
        self.watchers[stash_name]["notifier"].stop()
        self.watchers.pop(stash_name)

        watch_file = os.path.join(
            xdg_config_home, ".carp", stash_name, "watched")
        if os.path.exists(watch_file):
            os.unlink(watch_file)

    def is_watched(self, stash_name):
        if stash_name in self.watchers:
            return True

        watch_file = os.path.join(
            xdg_config_home, ".carp", stash_name, "watched")
        if os.path.exists(watch_file):
            print(_("{0} seems to be watched by another process.")
                  .format(stash_name),
                  file=sys.stderr)
            return True

        return False


if __name__ == "__main__":
    print("CarpWatcher is not intended to be directly called",
          file=sys.stderr)
