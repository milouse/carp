#!/usr/bin/env python3

import os
import sys
from carp.stash_manager import StashManager, CarpNotAStashError, \
    CarpMountError, CarpNoRemoteError, CarpNotEmptyDirectoryError, \
    CarpSubcommandError, CarpMustBePushedError
from carp.version import VERSION
from xdg.BaseDirectory import xdg_config_home
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import gettext
CARP_L10N_PATH = "./locales"
# Explicit declaration to avoid flake8 fear.
gettext.bindtextdomain("carp", CARP_L10N_PATH)
gettext.textdomain("carp")
_ = gettext.gettext


class CarpCli:
    def __init__(self):
        self.parse_args()

        config_file = os.path.join(xdg_config_home, ".carp", "carp.conf")
        if self.options["config"]:
            config_file = os.path.expanduser(self.options["config"])

        if self.command not in dir(StashManager):
            self.die(_("WTF command not recognized!"))

        try:
            carp = StashManager(config_file)
        except (FileNotFoundError, NotADirectoryError,
                CarpNotEmptyDirectoryError) as e:
            self.die(str(e))

        if self.command in ["mount", "umount", "pull", "push"] and \
           "stash" in self.options and self.options["stash"] == "all":
            work_on_stash = []
            if self.command == "umount":
                work_on_stash = carp.mounted_stashes()
            else:
                work_on_stash = carp.unmounted_stashes()

            for st in work_on_stash:
                print(_("Working on {0}").format(st))
                self.options["stash"] = st
                self.run(carp, False)

        else:
            self.run(carp)

    def die(self, msg, error_code=1):
        print(msg, file=sys.stderr)
        sys.exit(error_code)

    def parse_args(self):
        carp_desc = _("EncFS CLI managing tool")
        parser = ArgumentParser(
            description=carp_desc,
            formatter_class=RawDescriptionHelpFormatter,
            epilog="""\
Each command has its own help. To access it, do a:
  %(prog)s command --help

For exemple: %(prog)s create --help
""")
        parser.add_argument("-v", "--version", action="store_true",
                            help="Display carp version information"
                                 " and exit.")
        parser.add_argument("-c", "--config",
                            help=_("Customized config file."))

        parent_parser = ArgumentParser(add_help=False)
        parent_parser.add_argument("stash", help="Stash to handle.")
        parent_parser.add_argument("-t", "--test",
                                   action="store_true",
                                   help="Dry-run.")

        subparsers = parser.add_subparsers(
            dest="command", title="Commands", help=None,
            metavar="what to do with your EncFS stashes:",
            description=None)
        parser_list = subparsers.add_parser(
            "list", help="List your EncFS stashes.")
        parser_create = subparsers.add_parser(
            "create", help="Create a new EncFS stash.")
        subparsers.add_parser(
            "mount", help="Mount an existing EncFS stash.",
            parents=[parent_parser])
        subparsers.add_parser(
            "umount", help="Unmount a currently mounted EncFS stash.",
            parents=[parent_parser])
        subparsers.add_parser(
            "pull", help="Pull a distant stash.",
            parents=[parent_parser])
        subparsers.add_parser(
            "push", help="Push a distant stash.",
            parents=[parent_parser])

        parser_create.add_argument(
            "-s", "--save-pass", action="store_true",
            help="Save the password in a file.")
        parser_create.add_argument(
            "-m", "--mount", action="store_true",
            help="Mount the stash after creation.")
        parser_create.add_argument(
            "rootdir", help="The path to an empty folder, which will "
            "become the encrypted stash.")

        parser_list.add_argument(
            "state", nargs="?", default="mounted",
            choices=["mounted", "unmounted", "all"],
            help="What do you want to list? (default: mounted)")
        parser_list.add_argument("-r", "--raw", action="store_true",
                                 help="Don't display stash current state "
                                 "(only useful for 'all' subcommand).")

        args = parser.parse_args()

        if args.version:
            print("{} - v{}".format(carp_desc, VERSION))
            sys.exit(0)

        self.command = args.command

        if self.command not in subparsers.choices.keys():
            self.die(parser.format_help())

        self.options = getattr(self, self.command)(args)
        self.options["config"] = args.config

    def list(self, opts):
        return {
            "state": opts.state,
            "raw": opts.raw
        }

    def get_stash(self, opts):
        return {
            "stash": opts.stash,
            "test": opts.test
        }

    def pull(self, opts):
        return self.get_stash(opts)

    def push(self, opts):
        return self.get_stash(opts)

    def mount(self, opts):
        return self.get_stash(opts)

    def umount(self, opts):
        return self.get_stash(opts)

    def create(self, opts):
        return {
            "rootdir": opts.rootdir,
            "mount": opts.mount,
            "save_pass": opts.save_pass
        }

    def run(self, carp, can_exit=True):
        try:
            if not getattr(carp, self.command)(self.options):
                if can_exit:
                    sys.exit(1)
                else:
                    return False

        except (NotADirectoryError, CarpNotAStashError,
                CarpMountError, CarpNoRemoteError,
                CarpNotEmptyDirectoryError, CarpSubcommandError,
                CarpMustBePushedError) as e:
            if can_exit:
                self.die(str(e))
            else:
                print(str(e))
                return False


if __name__ == "__main__":
    CarpCli()
