"""Build the menu-bar app with py2app."""

from setuptools import setup

APP = ["MemStat.py"]
OPTIONS = {
    "argv_emulation": False,
    "arch": "arm64",
    "plist": {
        "LSUIElement": True,
        "CFBundleName": "MemStat",
        "CFBundleDisplayName": "MemStat",
        "CFBundleShortVersionString": "1.1.0",
        "CFBundleVersion": "2",
    },
    "packages": ["rumps", "psutil", "AppKit"],
    "includes": ["memstat_core", "PyObjCTools.AppHelper"],
}

setup(
    app=APP,
    name="MemStat",
    version="1.1.0b1",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)