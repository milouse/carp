#!/usr/bin/env python3

import os
import re
import sys
import time
import shutil
import getpass
import subprocess
import inotify.adapters
from datetime import datetime
from configparser import ConfigParser
from xdg.BaseDirectory import xdg_config_home

import gettext
CARP_L10N_PATH = "./locales"
# Explicit declaration to avoid flake8 fear.
gettext.bindtextdomain("carp", CARP_L10N_PATH)
gettext.textdomain("carp")
_ = gettext.gettext

CARP_STASH_POSSIBLE_STATUS = {
    "-": "-",  # if it works it ain't stupid
    "mounted": _("mounted")
}

CARP_POSSIBLE_INOTIFY_STATUS = {
    "IN_CREATE": _("{} created"),
    "IN_DELETE": _("{} deleted"),
    "IN_MODIFY": _("{} modified"),
    "IN_MOVED": _("{} moved")
}


class CarpNotAStashError(Exception):
    pass


class CarpMountError(Exception):
    pass


class CarpNoRemoteError(Exception):
    pass


class CarpNotEmptyDirectoryError(Exception):
    pass


class CarpSubcommandError(Exception):
    pass


class CarpMustBePushedError(Exception):
    pass


class StashManager:
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = ConfigParser()
        self.config.read(self.config_file)

        if "general" not in self.config:
            self.config["general"] = {}

        self._mount_point = None
        self.config["general"]["mount_point"] = self.mount_point()
        self._encfs_root = None
        self.config["general"]["encfs_root"] = self.encfs_root()

        self.write_config()
        self.reload_stashes()

    def reload_stashes(self):
        self.stashes = {}
        for sec in self.config.sections():
            loc_emp = self.init_stash(sec)
            if loc_emp:
                self.stashes[sec] = loc_emp

    def init_stash(self, stash_name):
        if stash_name == "general":
            return None

        config_dir = os.path.join(xdg_config_home, ".carp", stash_name)
        if "config_path" in self.config[stash_name]:
            config_dir = self.config[stash_name]["config_path"]

        config_dir = self.check_dir(os.path.expanduser(config_dir))

        config_file = os.path.join(config_dir, "encfs6.xml")
        if not os.path.exists(config_file):
            raise FileNotFoundError(
                _("{0} does not exists.").format(config_file))

        pass_file = os.path.join(config_dir, "encfs.pass.gpg")
        if not os.path.exists(pass_file):
            pass_file = None
        else:
            os.chmod(pass_file, 0o600)

        os.chmod(config_file, 0o600)

        stash_remote_path = None
        if "remote_path" in self.config[stash_name] and \
           "nosync" not in self.config[stash_name]:
            stash_remote_path = self.config[stash_name]["remote_path"]

        stash_encfs_root = os.path.join(self.encfs_root(), stash_name)
        if "encfs_root" in self.config[stash_name]:
            stash_encfs_root = os.path.expanduser(
                self.config[stash_name]["encfs_root"])

        if not os.path.exists(stash_encfs_root):
            raise FileNotFoundError(
                _("{0} does not exists.").format(stash_encfs_root))

        return {"config_path": config_dir,
                "config_file": config_file,
                "pass_file": pass_file,
                "remote_path": stash_remote_path,
                "encfs_root": stash_encfs_root}

    def check_dir(self, path):
        if (os.path.exists(path) and
           not os.path.isdir(path)):
            raise NotADirectoryError(
                _("{0} already exists in your file system but is "
                  "NOT an empty folder.").format(path))
        elif not os.path.exists(path):
            print(_("WARNING: {0} does not exists, "
                    "thus we create an empty one")
                  .format(path), file=sys.stderr)
            os.makedirs(path)

        return path

    def check_dir_is_empty(self, path):
        if any(os.listdir(path)):
            raise CarpNotEmptyDirectoryError(
                _("{0} is not an empty dirctory. It cannot be used as a "
                  "new EncFS stash.").format(path))

    def mount_point(self):
        if self._mount_point:
            return self._mount_point

        self._mount_point = os.path.join(os.path.expanduser("~"), "Private")

        if ("general" in self.config and
           "mount_point" in self.config["general"]):
            self._mount_point = self.config["general"]["mount_point"]

        return self.check_dir(self._mount_point)

    def encfs_root(self):
        if self._encfs_root:
            return self._encfs_root

        self._encfs_root = os.path.join(os.path.expanduser("~"), ".encfs_root")

        if ("general" in self.config and
           "encfs_root" in self.config["general"]):
            self._encfs_root = self.config["general"]["encfs_root"]

        return self.check_dir(self._encfs_root)

    def write_config(self):
        with open(self.config_file, "w") as f:
            self.config.write(f)

    def log_activity(self, stash_name, activity):
        config_dir = os.path.join(xdg_config_home, ".carp", stash_name)
        log_file = os.path.join(config_dir, "activity.log")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a") as f:
            f.write("[{0}] {1}\n".format(now, activity))

        rotate_file = False
        with open(log_file, "r") as f:
            all_lines_count = sum(1 for _ in f)
            if all_lines_count > 500:
                rotate_file = True

        if rotate_file:
            shutil.copyfile(log_file, log_file + ".1")
            os.truncate(log_file, 0)

    def valid_stash(self, stash_name):
        if stash_name not in self.stashes.keys():
            raise CarpNotAStashError(_("{0} is not a known stash.")
                                     .format(stash_name))

    def mounted_stashes(self):
        all_stashes = self.stashes.keys()
        _mounted_stashes = []

        with open("/proc/mounts", "r") as proc:
            for line in proc:
                regex = r"^encfs {}/(.+) fuse.encfs.+$" \
                        .format(self.mount_point())
                cdata = re.match(regex, line)
                if cdata is None:
                    continue
                lst = cdata.group(1)
                if lst not in all_stashes:
                    continue
                _mounted_stashes.append(lst)

        return _mounted_stashes

    def unmounted_stashes(self):
        return [st for st in self.stashes.keys()
                if st not in self.mounted_stashes()]

    def file_space_usage(self, stash_name):
        encfs_mp = self.stashes[stash_name]["encfs_root"]
        cmd = subprocess.run(["du", "-sh", encfs_mp],
                             check=True, stdout=subprocess.PIPE)
        return re.sub(encfs_mp, "", cmd.stdout.decode()).strip()

    def __format_stash(self, stash_name, state="mounted", no_state=False):
        pdata = [stash_name]
        lin_home = os.path.expanduser("~")

        if not no_state:
            pdata.append(CARP_STASH_POSSIBLE_STATUS[state])

        encfs_mp = self.stashes[stash_name]["encfs_root"]
        if os.path.exists(encfs_mp):
            pdata.append(re.sub(lin_home, "~", encfs_mp))
        else:
            pdata.append("ERR")

        if not no_state:
            stash_mount_point = os.path.join(self.mount_point(), stash_name)
            if state != "mounted":
                pdata.append("-")
            elif os.path.exists(stash_mount_point):
                pdata.append(re.sub(lin_home, "~", stash_mount_point))
            else:
                pdata.append("ERR")

        if self.stashes[stash_name]["remote_path"]:
            pdata.append(self.stashes[stash_name]["remote_path"])
        else:
            pdata.append("-")

        pdata.append(self.file_space_usage(stash_name))

        return tuple(pdata)

    def __list_raw(self, state, mounted_list, unmounted_list):
        if state == "mounted":
            print("\n".join(mounted_list))

        elif state == "unmounted":
            print("\n".join(unmounted_list))

        else:
            print("\n".join(mounted_list + unmounted_list))

        return True

    def __list_fancy(self, state, mounted_list, unmounted_list):
        name_len = len(_("NAME"))
        mounted_len = len(_("PATH"))
        remote_len = len(_("REMOTE"))
        root_len = len(_("ROOT"))
        lin_home = os.path.expanduser("~")

        state_len = len(_("STATE"))
        for i18n_state in CARP_STASH_POSSIBLE_STATUS.values():
            if len(i18n_state) > state_len:
                state_len = len(i18n_state)

        for st in self.stashes.keys():
            if (state == "mounted" and
               st not in mounted_list):
                continue
            if (state == "unmounted" and
               st not in unmounted_list):
                continue

            if len(st) > name_len:
                name_len = len(st)

            stash_mount_point = os.path.join(self.mount_point(), st)
            if os.path.exists(stash_mount_point) and st in mounted_list:
                stash_mount_point = re.sub(lin_home, "~", stash_mount_point)
                if len(stash_mount_point) > mounted_len:
                    mounted_len = len(stash_mount_point)

            encfs_mp = self.stashes[st]["encfs_root"]
            if os.path.exists(encfs_mp):
                encfs_mp = re.sub(lin_home, "~", encfs_mp)
                if len(encfs_mp) > root_len:
                    root_len = len(encfs_mp)

            stash_remote_path = self.stashes[st]["remote_path"]
            if stash_remote_path and len(stash_remote_path) > remote_len:
                    remote_len = len(stash_remote_path)

        partial_line = "{:<{nfill}} {:<{rfill}} {:<{refill}} {:<7}"
        complete_line = "{:<{nfill}} {:<{sfill}} {:<{rfill}} " \
                        "{:<{mfill}} {:<{refill}} {:<7}"

        if state == "unmounted":
            print(partial_line.format(_("NAME"), _("ROOT"), _("REMOTE"),
                                      _("SIZE"), nfill=name_len,
                                      rfill=root_len, refill=remote_len))

        else:
            print(complete_line.format(_("NAME"), _("STATE"), _("ROOT"),
                                       _("PATH"), _("REMOTE"), _("SIZE"),
                                       nfill=name_len,
                                       sfill=state_len,
                                       rfill=root_len,
                                       mfill=mounted_len,
                                       refill=remote_len))

        if state == "mounted" or state == "all":
            for st in mounted_list:
                print(complete_line.format(*self.__format_stash(st),
                                           nfill=name_len,
                                           sfill=state_len,
                                           rfill=root_len,
                                           mfill=mounted_len,
                                           refill=remote_len))
        elif state == "unmounted":
            for st in unmounted_list:
                print(partial_line.format(*self.__format_stash(st, "-", True),
                                          nfill=name_len,
                                          rfill=root_len,
                                          refill=remote_len))

        if state == "all":
            for st in unmounted_list:
                print(complete_line.format(*self.__format_stash(st, "-"),
                                           nfill=name_len,
                                           sfill=state_len,
                                           rfill=root_len,
                                           mfill=mounted_len,
                                           refill=remote_len))
        return True

    def list(self, opts):
        state = "mounted"
        if ("state" in opts and
           opts["state"] in ["mounted", "unmounted", "all"]):
            state = opts["state"]

        loc_mounted = self.mounted_stashes()
        loc_unmounted = self.unmounted_stashes()

        if state == "mounted" and not any(loc_mounted):
            return True

        elif state == "unmounted" and not any(loc_unmounted):
            return True

        elif (state == "all" and
              not any(loc_mounted) and
              not any(loc_unmounted)):
            return True

        if "raw" in opts and opts["raw"]:
            return self.__list_raw(state, loc_mounted, loc_unmounted)

        return self.__list_fancy(state, loc_mounted, loc_unmounted)

    def create(self, opts):
        stash_encfs_root = self.check_dir(
            os.path.expanduser(opts["rootdir"]))
        self.check_dir_is_empty(stash_encfs_root)

        stash_name = os.path.basename(stash_encfs_root)
        stash_mount_point = self.check_dir(
            os.path.join(self.mount_point(), stash_name))
        self.check_dir_is_empty(stash_mount_point)

        cmd = subprocess.run(["encfs", stash_encfs_root,
                              stash_mount_point])
        if cmd.returncode != 0:
            raise CarpSubcommandError(_("Something went wrong with EncFS"))

        time.sleep(2)
        subprocess.run(["fusermount", "-u", stash_mount_point])

        print(_("EncFS stash successfully created. "
                "Time to save new configuration."))

        old_config = os.path.join(stash_encfs_root, ".encfs6.xml")
        config_dir = self.check_dir(
            os.path.join(xdg_config_home, ".carp", stash_name))
        new_config = os.path.join(config_dir, "encfs6.xml")
        shutil.move(old_config, new_config)
        os.chmod(new_config, 0o600)

        self.config[stash_name] = {}
        self.write_config()

        if "save_pass" in opts and opts["save_pass"]:
            new_pass = os.path.join(config_dir, "encfs.pass.gpg")
            print(_("Please enter your password a last time in order "
                    "to save it in your home folder. Leave it blank "
                    "and press enter if you changed your mind."))
            loc_password = getpass.getpass("Password > ")
            loc_dest = input("gpg key id > ")
            if loc_password != "":
                cmd = subprocess.Popen(
                    ["gpg", "-e", "-r", loc_dest, "-o", new_pass],
                    stdin=subprocess.PIPE)
                cmd.communicate(loc_password.encode())

                if cmd.returncode == 0:
                    os.chmod(new_pass, 0o600)

                else:
                    raise CarpSubcommandError(
                        _("Something went wrong while saving your password."))

        if "mount" in opts and opts["mount"]:
            opts["stash"] = stash_name
            self.stashes[stash_name] = self.init_stash(stash_name)
            return self.mount(opts)

        return True

    def may_sync(self, stash_name):
        if stash_name not in self.stashes:
            return False
        if not self.stashes[stash_name]["remote_path"]:
            return False
        if "nosync" in self.stashes[stash_name]:
            return False
        return True

    def handle_inotify_event(self, event, stash_name):
        (_, type_names, watch_path, filename) = event

        main_activity = None
        if "IN_UNMOUNT" in type_names:
            return 0
        elif "IN_CREATE" in type_names:
            main_activity = "IN_CREATE"
        elif "IN_DELETE" in type_names or "IN_DELETE_SELF" in type_names:
            main_activity = "IN_DELETE"
        elif "IN_MODIFY" in type_names or "IN_CLOSE_WRITE" in type_names:
            main_activity = "IN_MODIFY"
        elif "IN_MOVED_FROM" in type_names or "IN_MOVED_TO" in type_names or \
             "IN_MOVE_SELF" in type_names:
            main_activity = "IN_MOVED"
        else:
            return 2

        message = CARP_POSSIBLE_INOTIFY_STATUS[main_activity].format(
            os.path.join(watch_path, filename).decode("utf-8"))
        self.log_activity(stash_name, message)
        return 1

    def inotify_push_stash(self, stash_name):
        cmd = subprocess.run(["pgrep", "-u", getpass.getuser(), "rsync"])
        if cmd.returncode == 0:
            self.log_activity(stash_name, "Sync already running")
            return True

        self.log_activity(stash_name, "Will sync NOW")
        self.push({"stash": stash_name, "test": False, "quiet": True})
        return False

    def inotify_loop(self, stash_name, stash_mount_point):
        i = inotify.adapters.InotifyTree(stash_mount_point.encode("utf-8"))

        must_sync = False
        sync_wait = 10

        # And see the corresponding events:
        for event in i.event_gen():
            if sync_wait == 0:
                sync_wait = 10
                if must_sync:
                    must_sync = self.inotify_push_stash(stash_name)
            else:
                sync_wait -= 1

            if event is None:
                continue

            must_continue = self.handle_inotify_event(event, stash_name)
            if must_continue == 0:
                break
            elif must_continue == 1:
                must_sync = True

        self.log_activity(stash_name, "Killing inotify daemon")

    def mount(self, opts):
        test_run = "test" in opts and opts["test"]
        stash_name = opts["stash"]
        self.valid_stash(stash_name)
        if stash_name in self.mounted_stashes():
            raise CarpMountError(_("{0} already mounted."
                                 .format(stash_name)))
        if "nosync" in opts:
            self.stashes[stash_name]["nosync"] = True

        loc_stash = self.stashes[stash_name]
        stash_mount_point = self.check_dir(
            os.path.join(self.mount_point(), stash_name))
        self.check_dir_is_empty(stash_mount_point)
        stash_encfs_root = self.stashes[stash_name]["encfs_root"]

        os.environ["ENCFS6_CONFIG"] = loc_stash["config_file"]
        if test_run:
            print(_("{0} should be mounted without problem (DRY RUN)")
                  .format(stash_mount_point))
            return True

        mount_cmd = ["encfs", stash_encfs_root, stash_mount_point]
        if loc_stash["pass_file"]:
            mount_cmd.insert(1, "--extpass")
            mount_cmd.insert(2, "gpg -q -d {}".format(loc_stash["pass_file"]))
        elif "pass_cmd" in opts and opts["pass_cmd"] != "":
            mount_cmd.insert(1, "--extpass")
            mount_cmd.insert(2, opts["pass_cmd"])

        success_mount = subprocess.run(mount_cmd).returncode

        if success_mount != 0:
            print("{0} NOT mounted".format(stash_mount_point))
            return False

        print(_("{0} mounted").format(stash_mount_point))

        if test_run or not self.may_sync(stash_name):
            # If we don't have to sync, quit early
            return True

        newpid = os.fork()
        if newpid == 0:
            # Child process, begin loop
            self.inotify_loop(stash_name, stash_mount_point)

        return True

    def umount(self, opts):
        test_run = "test" in opts and opts["test"]
        stash_name = opts["stash"]
        self.valid_stash(stash_name)
        if stash_name in self.unmounted_stashes():
            raise CarpMountError(_("{0} not mounted.")
                                 .format(stash_name))
        if "nosync" in opts:
            self.stashes[stash_name]["nosync"] = True

        stash_mount_point = os.path.join(self.mount_point(), stash_name)

        if test_run:
            print(_("{0} should be unmounted without problem (DRY RUN)")
                  .format(stash_mount_point))
            return True

        cmd = subprocess.run(
            ["fusermount", "-u", stash_mount_point])

        if cmd.returncode != 0:
            print(_("ERROR: Something strange happened with fusermount."
                    " {0} NOT unmounted")
                  .format(stash_mount_point))
            return False

        print(_("{0} unmounted").format(stash_mount_point))

        if self.may_sync(stash_name):
            self.log_activity(stash_name, "Will sync NOW")
            self.push({"stash": stash_name, "test": False})
        return True

    def rsync(self, opts, direction="pull"):
        stash_name = opts["stash"]
        self.valid_stash(stash_name)
        if direction == "pull" and stash_name in self.mounted_stashes():
            raise CarpMountError(
                _("{0} should not be pulled while being mounted.")
                .format(stash_name))
        if not self.stashes[stash_name]["remote_path"]:
            raise CarpNoRemoteError(_("No remote configured for {0}")
                                    .format(stash_name))

        av_opt = "-av"
        if "test" in opts and opts["test"]:
            av_opt = "-nav"

        stash_encfs_root = self.stashes[stash_name]["encfs_root"]
        if stash_encfs_root[-1:] != "/":
            stash_encfs_root += "/"

        stash_remote_path = self.stashes[stash_name]["remote_path"]
        if stash_remote_path[-1:] != "/":
            stash_remote_path += "/"

        rsync_cmd = ["rsync", av_opt, "--delete"]
        if direction == "push":
            rsync_cmd.append(stash_encfs_root)
            rsync_cmd.append(stash_remote_path)

        else:
            rsync_cmd.append(stash_remote_path)
            rsync_cmd.append(stash_encfs_root)

        print(" ".join(rsync_cmd))

        err_output = None  # Default
        if "quiet" in opts and opts["quiet"] is True:
            err_output = subprocess.DEVNULL
        cmd = subprocess.run(rsync_cmd, stderr=err_output)
        if cmd.returncode != 0:
            return False
        return True

    def pull(self, opts):
        return self.rsync(opts)

    def push(self, opts):
        return self.rsync(opts, "push")
