#!/usr/bin/env python

from distutils.core import setup
import os
import sys
import shutil


def main():

    SHARE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
            "share")

    data_files = []
    
    # don't trash the system icons!
    black_list = ['index.theme', 'index.theme~']

    for path, dirs, files in os.walk(SHARE_PATH):

        data_files.append(tuple((path.replace(SHARE_PATH,"share", 1),
            [os.path.join(path, file) for file in files if file not in
                black_list])))

    desktop_name = "caffeine.desktop"
    desktop_file = os.path.join("share", "applications", desktop_name)
    autostart_dir = os.path.join("etc", "xdg", "autostart")
    if not os.path.exists(autostart_dir):
        os.makedirs(autostart_dir)
    shutil.copy(desktop_file, autostart_dir)
    data_files.append(tuple(("/" + autostart_dir, [os.path.join(autostart_dir, desktop_name)])))

    setup(name="caffeine",
        version="2.5",
        description="""A status bar application able to temporarily prevent the activation of both the screensaver and the "sleep" powersaving mode.""",
        author="The Caffeine Developers",
        author_email="bnsmith@gmail.com",
        url="https://launchpad.net/caffeine",
        packages=["caffeine"],
        data_files=data_files,
        scripts=[os.path.join("bin", "caffeine")]
        )

if __name__ == "__main__":
    main()
