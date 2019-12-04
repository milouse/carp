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
# Uncomment the following line during development.
# Please, be cautious to NOT commit the following line uncommented.
# gettext.bindtextdomain("carp", "./locales")
gettext.textdomain("carp")
_ = gettext.gettext

CARP_STASH_POSSIBLE_STATUS = {
    "-": "-",  # if it works it ain't stupid
    "mounted": _("mounted")
}

CARP_POSSIBLE_INOTIFY_STATUS = {
    "IN_CREATE": "created",
    "IN_DELETE": "deleted",
    "IN_MODIFY": "modified",
    "IN_MOVED": "moved"
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

        self.mount_point = self.check_and_clean_dir_path(
            self.config["general"].get(
                "mount_point", os.path.join("~", "Private")
            )
        )
        self.config["general"]["mount_point"] = self.mount_point

        self.encfs_root = self.check_and_clean_dir_path(
            self.config["general"].get(
                "encfs_root", os.path.join("~", ".encfs_root")
            )
        )
        self.config["general"]["encfs_root"] = self.encfs_root

        self.write_config()
        self.reload_stashes()

    def reload_stashes(self):
        self.stashes = {}
        for sec in self.config.sections():
            if sec == "general":
                continue
            self.stashes[sec] = self.init_stash(sec)

    def init_stash(self, stash_name):
        config_dir = self.stash_config_path(stash_name)

        config_file = os.path.join(config_dir, "encfs6.xml")
        if not os.path.exists(config_file):
            raise FileNotFoundError(
                _("{0} does not exists.").format(config_file))
        if oct(os.stat(config_file).st_mode & 0o777) != 0o600:
            os.chmod(config_file, 0o600)

        pass_file = os.path.join(config_dir, "encfs.pass.gpg")
        if not os.path.exists(pass_file):
            pass_file = None
        elif oct(os.stat(pass_file).st_mode & 0o777) != 0o600:
            os.chmod(pass_file, 0o600)

        stash_remote_path = None
        if not self.config[stash_name].get("nosync", False):
            stash_remote_path = self.config[stash_name].get("remote_path")

        stash_encfs_root = self.config[stash_name].get("encfs_root")
        if stash_encfs_root is None:
            stash_encfs_root = os.path.join(self.encfs_root, stash_name)
        else:
            stash_encfs_root = os.path.expanduser(stash_encfs_root)

        if not os.path.exists(stash_encfs_root):
            raise FileNotFoundError(
                _("{0} does not exists.").format(stash_encfs_root))

        return {"config_path": config_dir,
                "config_file": config_file,
                "pass_file": pass_file,
                "remote_path": stash_remote_path,
                "encfs_root": stash_encfs_root}

    def stash_config_path(self, stash_name):
        return self.check_and_clean_dir_path(
            self.config.get(stash_name, {}).get(
                "config_path",
                os.path.join(xdg_config_home, "carp", stash_name)
            )
        )

    def check_and_clean_dir_path(self, path, check_if_empty=False):
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            # path does not exists yet.
            print(_("WARNING: {0} does not exists, "
                    "thus we create an empty one")
                  .format(path), file=sys.stderr)
            os.makedirs(path)
        elif not os.path.isdir(path):
            raise NotADirectoryError(
                _("{0} already exists in your file system but is "
                  "NOT an empty folder.").format(path))
        if check_if_empty and any(os.listdir(path)):
            raise CarpNotEmptyDirectoryError(
                _("{0} is not an empty dirctory. It cannot be used as a "
                  "new EncFS stash.").format(path))
        return path

    def write_config(self):
        with open(self.config_file, "w") as f:
            self.config.write(f)

    def log_activity(self, stash_name, activity):
        config_dir = self.stashes[stash_name]["config_path"]
        log_file = os.path.join(config_dir, "activity.log")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a") as f:
            f.write("[{0}] {1}\n".format(now, activity))

        rotate_file = False
        if sum(1 for _line in open(log_file, "r")) > 500:
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
                        .format(self.mount_point)
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

    def _format_stash(self, stash_name, state="mounted", no_state=False):
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
            stash_mount_point = os.path.join(self.mount_point, stash_name)
            if state != "mounted":
                pdata.append("-")
            elif os.path.exists(stash_mount_point):
                pdata.append(re.sub(lin_home, "~", stash_mount_point))
            else:
                pdata.append("ERR")

        if self.stashes[stash_name]["remote_path"] is not None:
            pdata.append(self.stashes[stash_name]["remote_path"])
        else:
            pdata.append("-")

        pdata.append(self.file_space_usage(stash_name))

        return tuple(pdata)

    def _list_raw(self, state, mounted_list, unmounted_list):
        if state == "mounted":
            print("\n".join(mounted_list))
        elif state == "unmounted":
            print("\n".join(unmounted_list))
        else:
            print("\n".join(mounted_list + unmounted_list))
        return True

    def _list_fancy(self, state, mounted_list, unmounted_list):
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
            if state == "mounted" and st not in mounted_list:
                continue
            if state == "unmounted" and st not in unmounted_list:
                continue

            if len(st) > name_len:
                name_len = len(st)

            stash_mount_point = os.path.join(self.mount_point, st)
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

        if state == "unmounted":
            partial_line = "{:<{nfill}} {:<{rfill}} {:<{refill}} {:<7}"
            print(partial_line.format(_("NAME"), _("ROOT"), _("REMOTE"),
                                      _("SIZE"), nfill=name_len,
                                      rfill=root_len, refill=remote_len))
            for st in unmounted_list:
                print(partial_line.format(*self._format_stash(st, "-", True),
                                          nfill=name_len,
                                          rfill=root_len,
                                          refill=remote_len))
            return True

        complete_line = "{:<{nfill}} {:<{sfill}} {:<{rfill}} " \
                        "{:<{mfill}} {:<{refill}} {:<7}"

        print(complete_line.format(_("NAME"), _("STATE"), _("ROOT"),
                                   _("PATH"), _("REMOTE"), _("SIZE"),
                                   nfill=name_len, sfill=state_len,
                                   rfill=root_len, mfill=mounted_len,
                                   refill=remote_len))
        for st in mounted_list:
            print(complete_line.format(*self._format_stash(st),
                                       nfill=name_len, sfill=state_len,
                                       rfill=root_len, mfill=mounted_len,
                                       refill=remote_len))
        if state == "all":
            for st in unmounted_list:
                print(complete_line.format(*self._format_stash(st, "-"),
                                           nfill=name_len, sfill=state_len,
                                           rfill=root_len, mfill=mounted_len,
                                           refill=remote_len))
        return True

    def list(self, opts):
        state = opts.get("state")
        if state not in ["mounted", "unmounted", "all"]:
            state = "mounted"

        loc_mounted = self.mounted_stashes()
        loc_unmounted = self.unmounted_stashes()
        has_mounted = any(loc_mounted)
        has_unmounted = any(loc_unmounted)

        if state == "mounted" and not has_mounted:
            return True

        elif state == "unmounted" and not has_unmounted:
            return True

        elif state == "all" and not has_mounted and not has_unmounted:
            return True

        if opts.get("raw", False):
            return self._list_raw(state, loc_mounted, loc_unmounted)

        return self._list_fancy(state, loc_mounted, loc_unmounted)

    def create(self, opts):
        stash_encfs_root = self.check_and_clean_dir_path(
            opts["rootdir"], True
        )
        stash_name = os.path.basename(stash_encfs_root)
        stash_mount_point = self.check_and_clean_dir_path(
            os.path.join(self.mount_point, stash_name),
            True
        )

        cmd = subprocess.run(["encfs", stash_encfs_root,
                              stash_mount_point])
        if cmd.returncode != 0:
            raise CarpSubcommandError(_("Something went wrong with EncFS"))

        time.sleep(2)
        subprocess.run(["fusermount", "-u", stash_mount_point])

        print(_("EncFS stash successfully created. "
                "Time to save new configuration."))

        old_config = os.path.join(stash_encfs_root, ".encfs6.xml")
        config_dir = self.stash_config_path(stash_name)
        new_config = os.path.join(config_dir, "encfs6.xml")
        shutil.move(old_config, new_config)
        os.chmod(new_config, 0o600)

        self.config.setdefault(stash_name, {})
        self.write_config()

        if opts.get("save_pass", False):
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

        if opts.get("mount", False):
            opts["stash"] = stash_name
            self.stashes[stash_name] = self.init_stash(stash_name)
            return self.mount(opts)

        return True

    def may_sync(self, stash_name):
        if self.stashes[stash_name]["remote_path"] is None:
            return False
        return not self.stashes[stash_name].get("nosync", False)

    def handle_inotify_event(self, event, stash_name):
        (_data, type_names, watch_path, filename) = event

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

        message = "{} {}".format(
            os.path.join(watch_path, filename),
            CARP_POSSIBLE_INOTIFY_STATUS[main_activity]
        )
        self.log_activity(stash_name, message)
        return 1

    def inotify_push_stash(self, stash_name):
        cmd = subprocess.run(["pgrep", "-u", getpass.getuser(), "rsync"],
                             stdout=subprocess.DEVNULL)
        if cmd.returncode == 0:
            self.log_activity(stash_name, "Sync already running")
            return True

        self.log_activity(stash_name, "Will sync NOW")
        self.push({"stash": stash_name, "test": False, "quiet": True})
        return False

    def inotify_loop(self, stash_name, stash_mount_point):
        i = inotify.adapters.InotifyTree(stash_mount_point)

        must_sync = False
        sync_wait = 10

        # And see the corresponding events:
        for event in i.event_gen(terminal_events=('IN_Q_OVERFLOW')):
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

    def daemonize(self):
        """
        do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        https://web.archive.org/web/20131017130434/http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/
        """
        newpid = os.fork()
        if newpid > 0:
            return False
        # decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)
        # Fork a second time
        newpid = os.fork()
        if newpid > 0:
            return False
        return True

    def mount(self, opts):
        test_run = opts.get("test", False)
        stash_name = opts["stash"]
        self.valid_stash(stash_name)
        if stash_name in self.mounted_stashes():
            raise CarpMountError(_("{0} already mounted."
                                 .format(stash_name)))
        if opts.get("nosync", False):
            self.stashes[stash_name]["nosync"] = True

        stash_mount_point = self.check_and_clean_dir_path(
            os.path.join(self.mount_point, stash_name),
            True
        )
        stash_encfs_root = self.stashes[stash_name]["encfs_root"]

        os.environ["ENCFS6_CONFIG"] = self.stashes[stash_name]["config_file"]
        if test_run:
            print(_("{0} should be mounted without problem (DRY RUN)")
                  .format(stash_mount_point))
            return True

        mount_cmd = ["encfs", stash_encfs_root, stash_mount_point]
        if self.stashes[stash_name]["pass_file"]:
            mount_cmd.insert(1, "--extpass")
            mount_cmd.insert(
                2, "gpg -q -d {}".format(self.stashes[stash_name]["pass_file"])
            )
        elif opts.get("pass_cmd", "") != "":
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

        if self.daemonize():
            # Child process, begin loop
            self.inotify_loop(stash_name, stash_mount_point)

        return True

    def umount(self, opts):
        stash_name = opts["stash"]
        self.valid_stash(stash_name)
        if stash_name in self.unmounted_stashes():
            raise CarpMountError(_("{0} not mounted.")
                                 .format(stash_name))
        if opts.get("nosync", False):
            self.stashes[stash_name]["nosync"] = True

        stash_mount_point = os.path.join(self.mount_point, stash_name)

        if opts.get("test", False):
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

        if "quiet" in opts and opts["quiet"] is True:
            rsync_cmd.insert(1, "-q")
        else:
            print(" ".join(rsync_cmd))

        cmd = subprocess.run(rsync_cmd)
        if cmd.returncode != 0:
            return False
        return True

    def pull(self, opts):
        return self.rsync(opts)

    def push(self, opts):
        return self.rsync(opts, "push")
