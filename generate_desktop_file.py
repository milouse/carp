import os
import gettext
from carp import __description__, __generic_name__


def write_key(key, value):
    lines = []
    for l18ndir in os.listdir("./locales"):
        if l18ndir == "carp.pot":
            continue
        loc_lang = gettext.translation(
            "carp", localedir="./locales",
            languages=[l18ndir])
        loc_lang.install()
        lines.append("{0}[{1}]={2}".format(
            key, l18ndir, loc_lang.gettext(value)))
    return lines


def generate_desktop_file():
    df_content = ["[Desktop Entry]"]
    loc_lang = gettext.translation(
        "carp", localedir="./locales",
        languages=["en_US"])
    loc_lang.install()
    _ = loc_lang.gettext
    # Copy english description string
    df_content.append("Name={}".format("Carp"))
    df_content.append("GenericName={}".format(_(__generic_name__)))
    df_content.append("Comment={}".format(_(__description__)))
    df_content += write_key("Name", "Carp")
    df_content += write_key("GenericName", __generic_name__)
    df_content += write_key("Comment", __description__)
    with open("./carp.desktop", "w") as lnfile:
        lnfile.write("\n".join(df_content))
        lnfile.write("""
Exec=carp-icon
Icon=carp
Terminal=false
Type=Application
Categories=Network;
StartupNotify=false
""")


if __name__ == "__main__":
    generate_desktop_file()
