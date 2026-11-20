# MemStat

**A compact memory monitor for the macOS menu bar. Apple Silicon only (M-series Macs).**

MemStat shows memory usage in the menu bar, groups related application processes, and lets you inspect or safely request termination of individual processes. It uses a native macOS menu rather than a separate window.

> **Release status:** v1.1.0-beta.1 is a preview release. The existing v1.0.0 download is the older design. Download the new **MemStat-AppleSilicon.zip** from the [Releases page](https://github.com/roy8in/memstat/releases) after the new preview release is published.

## 1. Install (no Python or Terminal required)

1. Open **[GitHub Releases](https://github.com/roy8in/memstat/releases)**.
2. Select **MemStat v1.1.0-beta.1 (Apple Silicon)**. Do not download the older v1.0.0 build if you want the redesigned menu.
3. Under **Assets**, download **`MemStat-AppleSilicon.zip`**. The `.sha256` file is an optional checksum, not the app.
4. Double-click the ZIP to extract **`MemStat.app`**.
5. Drag **`MemStat.app`** into Finder → **Applications**.
6. Open **Applications → MemStat**. Look for the memory icon and percentage at the top right of the macOS menu bar. MemStat does **not** open a Dock icon or a separate window.

### If macOS blocks the first launch

Preview builds are **not Developer ID signed or Apple-notarized**. macOS may display a warning. If you obtained the app from this repository and trust the download:

1. Try opening the app normally in **Applications**.
2. If macOS blocks it, go to **System Settings → Privacy & Security**.
3. Scroll down to the security message about **MemStat** and choose **Open Anyway**, if available.
4. Confirm that you want to open the app.

Do not disable Gatekeeper globally or run commands that strip quarantine protection. Some managed Macs disallow unnotarized apps; if the **Open Anyway** option is unavailable, follow your organization's policies. This is a preview release, and installing it is at your discretion.

### Launch automatically at login (optional)

1. Open **System Settings → General → Login Items & Extensions** (the wording may differ by macOS version).
2. Under **Open at Login**, add **MemStat.app** from **Applications**.
3. MemStat will appear in the menu bar when you sign in.

## 2. How to use

**Menu bar:** The small memory symbol and percentage show **in-use RAM / total RAM**, not a warning or a direct indication of memory pressure. The symbol is monochrome to match other macOS menu-bar items.

**Open the menu:** Click the MemStat menu-bar item to see:

| Row | Meaning |
| --- | --- |
| Memory | RAM in use / total RAM, shown in **GiB**. The percentage in the menu bar uses these same numbers. |
| Memory Pressure | macOS pressure state (Normal / Warning / Critical), if available. Otherwise **Unavailable**. |
| Available | Memory that the system reports as available. |
| Wired | Wired RAM in use. |
| Compressed | Physical space occupied by the macOS memory compressor, read from `vm_stat`. **—** means the value is not available. |
| Swap Used | Swap space currently in use. |
| Top Applications | Groups of processes belonging to one recognized `.app` bundle. Other processes are shown individually. |

**View a process:** Open an application submenu to inspect its processes, current memory figures and PIDs. The first seven groups appear in the main menu; choose **More Applications & Processes** for additional groups. Use **Open Activity Monitor** for a complete system-wide view.

**Quit an application:** Where available, open the app submenu and choose **Quit Application…**. MemStat requests a normal application quit, after confirmation.

**Terminate a process:** Open **Application → Process → Terminate Process…**, read the confirmation, and confirm. The app checks the process PID, creation time and user account again before sending SIGTERM; it does not automatically force kill. Unsaved work in the affected application may be lost.

**Refresh:** When the menu is open, displayed values refresh periodically but the list order stays fixed to prevent moving targets. Close and reopen the menu to refresh which processes appear and their ordering.

### A note about app memory totals

Application totals are **summed RSS (resident set size)**. Shared memory can be counted multiple times, so this is *not* a precise measurement of unique RAM consumption or memory that closing the app will free. It may differ from Activity Monitor's **Memory** column.

## 3. Update MemStat

1. Click the menu-bar MemStat item and choose **Quit MemStat**.
2. Download the newer **`MemStat-AppleSilicon.zip`** from [Releases](https://github.com/roy8in/memstat/releases).
3. Extract the app and drag the new **MemStat.app** into **Applications**, selecting **Replace** when Finder asks.
4. Open MemStat again. If you added it to Login Items, check that the entry still points to the app in **Applications**.

MemStat does not currently update itself. No Python installation is required for released ZIP builds.

## 4. Uninstall

1. Choose **Quit MemStat** from its menu.
2. In **System Settings → General → Login Items & Extensions**, remove MemStat from **Open at Login** if you enabled it.
3. Drag **MemStat.app** out of **Applications** and into the Trash.

## 5. Troubleshooting

| Problem | What to check |
| --- | --- |
| No menu-bar item | Confirm MemStat is running in Activity Monitor; check for hidden menu-bar items if the menu bar is crowded. There is no Dock icon. |
| macOS prevents launch | Follow the **Privacy & Security → Open Anyway** steps above, subject to your Mac's security policy. |
| Memory Pressure says `Unavailable` | The system pressure interface is undocumented and may be unavailable. RAM figures still work. `Unavailable` is not the same as `Normal`. |
| Compressed says `—` | The background `vm_stat` query has not completed or failed. Reopen the menu. |
| Application is not grouped as expected | Process grouping relies on readable executable paths, app bundles and process ancestry. Some helper processes may remain separate. |
| Terminate fails | The process may have exited, changed identity, or be protected. Reopen the menu and check Activity Monitor. |
| Numbers differ from Activity Monitor | This app shows summed RSS for process groups, which is not the same metric as Activity Monitor's app memory footprint. |

Report reproducible issues in [GitHub Issues](https://github.com/roy8in/memstat/issues), ideally including the macOS version, MemStat version, and the exact message or screenshot. Avoid including sensitive process arguments or private data.

## 6. Build from source (developers)

Building the app is optional. **The release ZIP does not require Python.** To build from source, use an Apple Silicon Mac with Python 3.12 and the macOS command-line developer tools installed.

```bash
git clone https://github.com/roy8in/memstat.git
cd memstat
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python setup.py py2app
```

Copy **`dist/MemStat.app`** to **Applications**. This creates a local build, not a notarized distribution.

### Automated builds and releases

- Pull requests run tests and build a **native arm64** `.app` on an Apple Silicon macOS GitHub Actions runner.
- The workflow verifies that the executable is `arm64`, checks the menu-bar bundle configuration and packages **`MemStat-AppleSilicon.zip`**.
- Merging to `main` triggers the same checks and publishes the **v1.1.0-beta.1** preview release **only if the build succeeds**. A published version is not overwritten by later pushes.
- A passing CI build verifies packaging and imports, **not** interactive menu behavior or a successful first launch on a physical Mac. Please report any problems after installation.

## 7. Technical details and limitations

- Implementation: Python, rumps, PyObjC/AppKit, psutil, py2app.
- Supported architecture for this build: **Apple Silicon (`arm64`) only**. Tested by CI on the macOS 15 Apple Silicon runner; other macOS versions require real-device validation.
- The memory-percentage metric is `psutil.virtual_memory().used / total`, representing active + wired memory under the current macOS psutil implementation. It is **not** a Memory Pressure measurement.
- The Memory Pressure state uses an **undocumented macOS interface**, so it may show `Unavailable` on some systems.
- The app processes only processes accessible to the current account; it cannot replace Activity Monitor.
- The preview build is ad-hoc signed for native execution when built by py2app, but **not Apple Developer ID signed or notarized**.

© MemStat contributors. See repository history and GitHub Issues for changes and support.
