#!/usr/bin/env python3

import os
import sys
from pyinotify import WatchManager, Notifier, ProcessEvent, \
    IN_ATTRIB, IN_CLOSE_WRITE, IN_CREATE, IN_DELETE, \
    IN_MODIFY, IN_IGNORED
from carp.stash_manager import StashManager
from xdg.BaseDirectory import xdg_cache_home, xdg_config_home


class CarpStopNotifierError(Exception):
    pass


class CarpEventHandler(ProcessEvent):
    def __init__(self, config_file, stash_name):
        self.sm = StashManager(config_file)
        self.stash_name = stash_name
        self.should_stop = False

    def process_IN_IGNORED(self, event):
        print("{}: {}".format(event.maskname, event.pathname))
        stop_file = os.path.join(xdg_config_home, ".carp",
                                 self.stash_name, "watch_running")
        if event.pathname == stop_file:
            raise CarpStopNotifierError()

    def process_default(self, event):
        self.sm.reload_stashes()
        self.sm.write_timestamp(self.stash_name, "change")
        print("{}: {}".format(event.maskname, event.pathname))


class StashWatcher:
    def __init__(self, stash_name, config_file=None):
        self.stash_name = stash_name

        if not config_file:
            config_file = os.path.join(xdg_config_home,
                                       ".carp", "carp.conf")
        else:
            config_file = os.path.expanduser(config_file)

        wm = WatchManager()
        notifier = Notifier(
            wm, CarpEventHandler(config_file, self.stash_name))

        sm = StashManager(config_file)
        watch_mask = (IN_ATTRIB | IN_CLOSE_WRITE | IN_CREATE |
                      IN_DELETE | IN_MODIFY)
        wm.add_watch(sm.stashes[self.stash_name]["encfs_root"],
                     watch_mask,
                     rec=True)

        stop_file = os.path.join(xdg_config_home, ".carp",
                                 self.stash_name, "watch_running")
        open(stop_file, "w").close()
        wm.add_watch(stop_file, IN_IGNORED)

        pid_file = os.path.join(xdg_cache_home,
                                "carp_watcher.{}.pid"
                                .format(self.stash_name))
        log_file = os.path.join(xdg_config_home, ".carp",
                                self.stash_name, "carp_watcher.log")
        with open(log_file, "w") as f:
            f.write("Watch start for {}\n".format(self.stash_name))

        try:
            notifier.loop(daemonize=True, pid_file=pid_file,
                          stdout=log_file)
        except CarpStopNotifierError:

            with open(log_file, "a") as f:
                f.write("Watch end for {}\n".format(self.stash_name))


if __name__ == "__main__":
    if len(sys.argv) == 3:
        StashWatcher(sys.argv[1], sys.argv[2])
    else:
        StashWatcher(sys.argv[1])
