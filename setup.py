"""Build the menu-bar app with py2app."""

from setuptools import setup

APP = ["MemStat.py"]
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "LSUIElement": True,
        "CFBundleName": "MemStat",
        "CFBundleDisplayName": "MemStat",
    },
    "packages": ["rumps", "psutil", "AppKit"],
    "includes": ["memstat_core", "PyObjCTools.AppHelper"],
}

setup(
    app=APP,
    name="MemStat",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)