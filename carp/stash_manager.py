#!/usr/bin/env python3

import os
import re
import subprocess
from configparser import ConfigParser
from xdg.BaseDirectory import xdg_config_home


class CarpNotAStashError(Exception):
    pass


class CarpMountError(Exception):
    pass


class CarpNoRemoteError(Exception):
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

        self.stashes = {}
        for sec in self.config.sections():
            loc_emp = self.init_stash(sec)
            if loc_emp:
                self.stashes[sec] = loc_emp

        self.write_config()

    def init_stash(self, stash_name):
        if stash_name == "general":
            return None

        config_dir = os.path.join(xdg_config_home, ".carp", stash_name)
        if "config_path" in self.config[stash_name]:
            config_dir = self.config[stash_name]["config_path"]

        config_dir = self.check_dir(os.path.expanduser(config_dir))

        config_file = os.path.join(config_dir, "encfs6.xml")
        if not os.path.exists(config_file):
            print("{} does not exists.".format(config_file))
            return None

        pass_file = os.path.join(config_dir, "encfs.pass.gpg")
        if not os.path.exists(pass_file):
            pass_file = None

        remote_path = None
        if "remote_path" in self.config[stash_name]:
            remote_path = self.config[stash_name]["remote_path"]

        return {"config_path": config_dir,
                "config_file": config_file,
                "pass_file": pass_file,
                "remote_path": remote_path}

    def check_dir(self, path):
        if (os.path.exists(path) and
           not os.path.isdir(path)):
            raise NotADirectoryError(
                "{} already exists in your file system but is "
                "NOT an empty folder.".format(path))
        elif not os.path.exists(path):
            os.makedirs(path)

        return path

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

    def valid_stash(self, stash_name):
        if stash_name not in self.stashes.keys():
            raise CarpNotAStashError("{} is not a known stash."
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

    def format_stash(self, stash_name, state="mounted", no_state=False):
        pdata = [stash_name]
        lin_home = os.path.expanduser("~")

        if not no_state:
            pdata.append(state)

        encfs_mp = os.path.join(self.encfs_root(), stash_name)
        if os.path.exists(encfs_mp):
            pdata.append(re.sub(lin_home, "~", encfs_mp))
        else:
            pdata.append("ERR")

        cmd = subprocess.run(["du", "-sh", encfs_mp],
                             check=True, stdout=subprocess.PIPE)
        st_size = re.sub(encfs_mp, "", cmd.stdout.decode()).strip()
        pdata.append(st_size)

        if not no_state:
            final_mp = os.path.join(self.mount_point(), stash_name)
            if state != "mounted":
                pdata.append("-")
            elif os.path.exists(final_mp):
                pdata.append(re.sub(lin_home, "~", final_mp))
            else:
                pdata.append("ERR")

        if self.stashes[stash_name]["remote_path"]:
            pdata.append(self.stashes[stash_name]["remote_path"])
        else:
            pdata.append("-")

        return tuple(pdata)

    def list(self, opts):
        if (opts["state"] == "mounted" and
           not any(self.mounted_stashes())):
            return True
        elif (opts["state"] == "unmounted" and
              not any(self.unmounted_stashes())):
            return True
        elif (opts["state"] == "all" and
              not any(self.mounted_stashes()) and
              not any(self.unmounted_stashes())):
            return True

        if opts["raw"]:
            if opts["state"] == "mounted":
                print("\n".join(self.mounted_stashes()))

            elif opts["state"] == "unmounted":
                print("\n".join(self.unmounted_stashes()))

            else:
                print("\n".join(self.mounted_stashes()))
                print("\n".join(self.unmounted_stashes()))

            return True

        name_len = 4
        mounted_len = 4
        root_len = 4
        lin_home = os.path.expanduser("~")
        for st in self.stashes.keys():
            if len(st) > name_len:
                name_len = len(st)

            final_mp = os.path.join(self.mount_point(), st)
            if os.path.exists(final_mp) and st in self.mounted_stashes():
                final_mp = re.sub(lin_home, "~", final_mp)
                if len(final_mp) > mounted_len:
                    mounted_len = len(final_mp)

            encfs_mp = os.path.join(self.encfs_root(), st)
            if os.path.exists(encfs_mp):
                encfs_mp = re.sub(lin_home, "~", encfs_mp)
                if len(encfs_mp) > root_len:
                    root_len = len(encfs_mp)

        if opts["state"] == "unmounted":
            print("{:<{nfill}} {:<{rfill}} {:<7} {}"
                  .format("NAME", "ROOT", "SIZE", "REMOTE",
                          nfill=name_len, rfill=root_len))

        else:
            print("{:<{nfill}} {:<7} {:<{rfill}} {:<7} {:<{mfill}} {}"
                  .format("NAME", "STATE", "ROOT", "SIZE", "PATH",
                          "REMOTE", nfill=name_len, rfill=root_len,
                          mfill=mounted_len))

        if opts["state"] == "mounted" or opts["state"] == "all":
            for st in self.mounted_stashes():
                print("{:<{nfill}} {:<7} {:<{rfill}} "
                      "{:<7} {:<{mfill}} {}"
                      .format(*self.format_stash(st),
                              nfill=name_len, rfill=root_len,
                              mfill=mounted_len))
        elif opts["state"] == "unmounted":
            for st in self.unmounted_stashes():
                print("{:<{nfill}} {:<{rfill}} {:<7} {}"
                      .format(*self.format_stash(st, "-", True),
                              nfill=name_len, rfill=root_len))

        if opts["state"] == "all":
            for st in self.unmounted_stashes():
                print("{:<{nfill}} {:<7} {:<{rfill}} {:<7} "
                      "{:<{mfill}} {}"
                      .format(*self.format_stash(st, "-"),
                              nfill=name_len, rfill=root_len,
                              mfill=mounted_len))
        return True

    def mount(self, opts):
        self.valid_stash(opts["stash"])
        if opts["stash"] in self.mounted_stashes():
            raise CarpMountError("{} already mounted."
                                 .format(opts["stash"]))

        loc_stash = self.stashes[opts["stash"]]
        final_mount_point = self.check_dir(
            os.path.join(self.mount_point(), opts["stash"]))
        final_encfs_root = os.path.join(self.encfs_root(), opts["stash"])
        if not os.path.exists(final_encfs_root):
            raise FileNotFoundError(
                "{} does not exists.".format(final_encfs_root))

        success_mount = 1
        os.environ["ENCFS6_CONFIG"] = loc_stash["config_file"]
        if opts["test"]:
            print("{} should be mounted without problem (DRY RUN)"
                  .format(final_mount_point))
            return True

        if loc_stash["pass_file"]:
            gpg_pass = subprocess.run(
                ["gpg", "-d", loc_stash["pass_file"]],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL)
            cmd = subprocess.Popen(
                ["encfs", "-S", final_encfs_root, final_mount_point],
                stdin=subprocess.PIPE)
            cmd.communicate(gpg_pass.stdout)
            success_mount = cmd.returncode

        else:
            success_mount = subprocess.run(
                ["encfs", final_encfs_root, final_mount_point],
                check=True
            ).returncode

        if success_mount == 0:
            print("{} mounted".format(final_mount_point))
            return True

        print("{} NOT mounted".format(final_mount_point))
        return False

    def unmount(self, opts):
        self.valid_stash(opts["stash"])
        if opts["stash"] in self.unmounted_stashes():
            raise CarpMountError("{} not mounted."
                                 .format(opts["stash"]))

        final_mount_point = os.path.join(self.mount_point(), opts["stash"])

        if opts["test"]:
            print("{} should be unmounted without problem (DRY RUN)"
                  .format(final_mount_point), 0)
            return True

        cmd = subprocess.run(
            ["fusermount", "-u", final_mount_point],
            check=True)

        if cmd.returncode == 0:
            print("{} unmounted".format(final_mount_point))
            return True

        print("An error happened, {} NOT unmounted"
              .format(final_mount_point))
        return False

    def rsync(self, opts, direction="pull"):
        self.valid_stash(opts["stash"])
        if opts["stash"] in self.mounted_stashes():
            raise CarpMountError(
                "{} should not be pulled while being mounted."
                .format(opts["stash"]))
        if not self.stashes[opts["stash"]]["remote_path"]:
            raise CarpNoRemoteError("No remote configured for {}"
                                    .format(opts["stash"]))

        av_opt = "-av"
        if opts["test"]:
            av_opt = "-nav"

        final_encfs_root = os.path.join(self.encfs_root(), opts["stash"])
        if final_encfs_root[-1:] != "/":
            final_encfs_root += "/"

        remote_path = self.stashes[opts["stash"]]["remote_path"]
        if remote_path[-1:] != "/":
            remote_path += "/"

        rsync_cmd = ["rsync", av_opt, "--delete"]
        if direction == "push":
            rsync_cmd.append(final_encfs_root)
            rsync_cmd.append(remote_path)

        else:
            rsync_cmd.append(remote_path)
            rsync_cmd.append(final_encfs_root)

        print(" ".join(rsync_cmd))

        cmd = subprocess.run(rsync_cmd, check=True)
        if cmd.returncode == 0:
            return True
        return False

    def pull(self, opts):
        return self.rsync(opts)

    def push(self, opts):
        return self.rsync(opts, "push")
