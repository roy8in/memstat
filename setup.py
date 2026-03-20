from setuptools import setup

APP = ['MemStat.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': True,
    'plist': {
        'LSUIElement': True,  # 독(Dock)에 아이콘을 표시하지 않음
    },
    'packages': ['rumps', 'psutil', 'AppKit'],
}

setup(
    app=APP,
    name='MemStat',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)