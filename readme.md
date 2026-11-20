# MemStat for macOS

A lightweight macOS menu-bar monitor for memory usage, memory pressure, and
memory-heavy applications. Built with Python, rumps, psutil, and PyObjC.

## What changed on `main` / development branches

The menu bar uses a small native memory symbol and a compact percentage, with
a percentage-only fallback for older macOS versions. The dropdown shows:

- **In-use RAM / total RAM**: the exact numbers used to compute the percentage
  shown in the menu bar, based on `psutil.virtual_memory().used` (active +
  wired on macOS). These are **GiB**, not decimal GB.
- **Memory pressure**: the macOS discrete system level (`Normal`, `Warning`,
  `Critical`), if available. MemStat attempts the undocumented
  `kern.memorystatus_vm_pressure_level` sysctl; if unavailable, it displays
  `Unavailable` instead of inferring health from RAM percentage.
- **Available, Wired, Compressed, Swap Used**: the compressor entry displays
  physical pages occupied by the compressor, sourced from `vm_stat`; on failure
  it shows `—`, never a misleading zero.
- **Top applications and processes**: known applications are grouped by their
  outer `.app` bundle, using executable paths and process ancestry. Processes
  without an identifiable application remain individual entries. The main menu
  displays seven groups and the More submenu displays up to 20 additional
  groups. Activity Monitor is available for the full system-wide list.

### Important: process-memory accounting

The application rows show **summed RSS (resident set size)**, not unique
physical RAM or Activity Monitor's *Memory* column. Shared pages may be counted
more than once when aggregating processes. Do not interpret an application's
summed RSS as the memory that terminating it will release.

Click an application to inspect individual processes and their PIDs. Individual
processes have a separate **Terminate Process…** action. If macOS exposes a
running application for the group, **Quit Application…** requests a graceful
application quit. Both operations ask for confirmation and verify that the
process PID, creation time, and account still match the sampled process. MemStat
will never use SIGKILL automatically. It excludes its own process and a small
list of sensitive system processes from manual termination.

## Install and run from source

A Mac and Python 3 are required. Create a virtual environment:

```bash
git clone https://github.com/roy8in/memstat.git
cd memstat
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Build the app:

```bash
python3 setup.py py2app
```

Move `dist/MemStat.app` into `/Applications`. To launch at login, add the app
under **System Settings → General → Login Items**.

**Release note:** The existing [v1.0.0 release](https://github.com/roy8in/memstat/releases/tag/v1.0.0)
was created on March 20, 2026. It predates the current development changes.
Do not assume its downloadable binary includes the updated design. Build from
source until an updated, tested release is published.

## Test

Core calculations and grouping logic are platform-independent:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q MemStat.py memstat_core.py
```

Run the built `.app` on macOS to validate status-item rendering, `NSMenu`
submenus, application metadata, menu updates, and quit confirmation. Linux
unit tests cannot validate Cocoa behavior or a macOS `.app` bundle.

## Compatibility and limitations

- SF Symbols are used when available. On older macOS releases, MemStat shows a
  compact percentage without the memory icon.
- The memory-pressure sysctl is an **undocumented Apple interface**. It may
  change or become unavailable in future macOS versions.
- Compressed usage is measured in the background; it may temporarily display
  `—` until the read finishes.
- While the menu is open, numbers refresh without changing row order. Close
  and reopen the menu to see newly started applications or changes in ranking.
- Menus group only readable processes owned by the current user. Activity
  Monitor provides the system-wide view and additional macOS measurements.
- The source files are not code signed or notarized; follow your organization's
  Gatekeeper policies rather than bypassing security controls.