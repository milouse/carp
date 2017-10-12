#!/usr/bin/env python3

# -*- coding: utf-8;mode: python -*-

# python stuff
import os
import sys
import glob
import gettext
import subprocess
from shutil import copyfile
from datetime import date
from carp.version import VERSION

CARP_L10N_PATH = "./locales"


def write_key(lnfile, key, value):
    for l18ndir in os.listdir(CARP_L10N_PATH):
        if l18ndir == "carp.pot":
            continue

        loc_lang = gettext.translation(
            "carp", localedir=CARP_L10N_PATH,
            languages=[l18ndir])
        loc_lang.install()
        lnfile.write("{0}[{1}]={2}\n".format(
            key, l18ndir, loc_lang.gettext(value)))


def generate_desktop_file():
    with open("./carp.desktop", "w") as lnfile:
        lnfile.write("[Desktop Entry]\n")

        loc_lang = gettext.translation(
            "carp", localedir=CARP_L10N_PATH,
            languages=["en_US"])
        loc_lang.install()
        _ = loc_lang.gettext
        lnfile.write("Name={}\n".format(_("Carp")))
        lnfile.write("GenericName={}\n".format(_("EncFS manager")))
        lnfile.write("Comment={}\n".format(_("EncFS GUI managing tool")))
        write_key(lnfile, "Name", "Carp")
        write_key(lnfile, "GenericName", "EncFS manager")
        write_key(lnfile, "Comment", "EncFS GUI managing tool")

        lnfile.write("""\
Exec=carp gui
Icon=carp
Terminal=false
Type=Application
Categories=Network;
StartupNotify=false
""")


def compile():
    for lang in os.listdir(CARP_L10N_PATH):
        if lang == "carp.pot":
            continue
        i18nfile = os.path.join(CARP_L10N_PATH, lang, "LC_MESSAGES", "carp.po")
        if not os.path.isfile(i18nfile):
            print("{} not found".format(i18nfile))
            continue

        mofile = os.path.join(CARP_L10N_PATH, lang, "LC_MESSAGES", "carp.mo")
        subprocess.run(["msgfmt", "-o", mofile, i18nfile])

    generate_desktop_file()


def get_potfile():
    if not os.path.isdir(CARP_L10N_PATH):
        os.makedirs(CARP_L10N_PATH)

    return os.path.join(CARP_L10N_PATH, "carp.pot")


def init():
    potfile = get_potfile()
    if os.path.isfile(potfile):
        os.unlink(potfile)

    gtcmd = ["xgettext", "--language=Python", "--keyword=_",
             "--keyword=N_", "--copyright-holder=Carp volunteers",
             "--package-name=Carp",
             "--package-version={}".format(VERSION),
             "--msgid-bugs-address=bugs@depar.is",
             "--from-code=UTF-8", "--output={}".format(potfile)]
    subprocess.run(gtcmd + glob.glob("carp/*.py"))

    subprocess.run(["sed", "-i", "-e",
                    "s|SOME DESCRIPTIVE TITLE.|Carp Translation Effort|",
                    "-e", "s|Content-Type: text/plain; charset=CHARSET|"
                    "Content-Type: text/plain; charset=UTF-8|",
                    "-e", "s|Copyright (C) YEAR|Copyright (C) {}|"
                    .format(date.today().year),
                    potfile])


def create(lang):
    potfile = get_potfile()
    i18nfile = os.path.join(CARP_L10N_PATH, lang, "LC_MESSAGES")
    if not os.path.isdir(i18nfile):
        os.makedirs(i18nfile)
    i18nfile = os.path.join(i18nfile, "carp.po")

    subprocess.run(["msginit", "-l", lang, "-i", potfile, "-o", i18nfile])


def update(lang):
    potfile = get_potfile()
    i18nfile = os.path.join(CARP_L10N_PATH, lang, "LC_MESSAGES", "carp.po")
    if not os.path.isfile(i18nfile):
        print("{} not found".format(i18nfile))
        sys.exit(1)

    oldi18nfile = os.path.join(CARP_L10N_PATH, lang,
                               "LC_MESSAGES", "carp.old.po")
    copyfile(i18nfile, oldi18nfile)

    subprocess.run(["msgmerge", "--lang", lang, "-o",
                    i18nfile, oldi18nfile, potfile])

    os.unlink(oldi18nfile)


if len(sys.argv) < 2 or not sys.argv[1] in globals():
    print("./generate_translations.py [ init | compile ]")
    print("./generate_translations.py [ create | update ] lang")
    sys.exit(1)

if len(sys.argv) == 3:
    globals()[sys.argv[1]](sys.argv[2])
    sys.exit(0)

globals()[sys.argv[1]]()
