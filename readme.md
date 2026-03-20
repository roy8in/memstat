# MemStat for macOS 🖥️

A lightweight, native-feeling macOS menu bar application to monitor your RAM usage in real-time and quickly terminate memory-hungry processes. 

![macOS Version](https://img.shields.io/badge/macOS-10.15%2B-blue)
![Python](https://img.shields.io/badge/Python-3.x-green)

---

## 🌟 Why MemStat?

macOS is great at managing memory, but sometimes a rogue app or browser tab can eat up your RAM and slow down your machine. MemStat lives quietly in your menu bar, showing you exactly how much memory is being used, and lets you kill heavy processes with a single click.

*   **Native Look & Feel**: Designed to look like an Apple built-in tool. Clean layout, perfectly aligned columns, and a minimal `●` icon that changes color based on system load.
*   **Zero CPU Overhead**: MemStat is smart. It only updates the heavy process list *while you are looking at the menu*. When the menu is closed, it takes virtually 0% CPU.
*   **One-Click Kill**: Click any process in the list to instantly kill it (with a safety confirmation prompt).

---

## 🚀 How to Install & Run

You don't need to know anything about coding to use this app. Just follow these simple steps:

### Option 1: Download the Ready-to-Use App (Easiest)

1. Go to the [**Releases**](https://github.com/roy8in/memstat/releases/tag/v1.0.0) section of this GitHub repository.
2. Unzip the file to get `MemStat.app`.
3. Drag and drop `MemStat.app` into your Mac's **Applications** (`/Applications`) folder.
4. **Important (Gatekeeper Bypass):** Because this app isn't signed by a paid Apple Developer account, macOS will block it the first time.
   * Open the Applications folder in Finder.
   * Hold the `Control` key on your keyboard and **click** `MemStat.app`, then select **Open**.
   * Click **Open** again on the warning prompt. (You only have to do this once).
5. Look at your top right menu bar—you'll see the MemStat icon (`●`)!

### Option 2: Build from Source (For Developers)

If you prefer to build the app yourself using Python:

1. Clone this repository:
   ```bash
   git clone https://github.com/roy8in/memstat.git
   cd memstat
   ```
2. Set up a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Build the macOS App:
   ```bash
   python3 setup.py py2app
   ```
4. Find the built app inside the `dist` folder and move it to `/Applications/`.

---

## ⚙️ Setting Up Auto-Start (Launch on Boot)

If you want MemStat to start automatically every time you turn on your Mac:

1. Click the **Apple Logo ()** in the top-left corner of your screen -> **System Settings**.
2. Go to **General** -> **Login Items**.
3. Under the **"Open at Login"** section, click the **`+`** button.
4. Navigate to your **Applications** folder, select **`MemStat.app`**, and click **Open**.

---

## 📖 How to Use

1. **Check Status**: Glance at the menu bar. The dot color tells you your RAM status:
   * 🟢 **Green**: Healthy (< 70% used)
   * 🟡 **Yellow**: Warning (70% - 90% used)
   * 🔴 **Red**: Critical (> 90% used, expect swapping and slowdowns)
2. **View Details**: Click the icon to see exactly how your memory is distributed (Wired, Compressed, Swap).
3. **Kill an App**: See an app using too much memory in the "Top Processes" list? Just click its name. A prompt will ask if you want to terminate it. Click "Terminate" and it's gone.

---

## 🛠 Tech Stack
*   **Language**: Python 3
*   **Libraries**: `rumps` (Menu bar wrapper), `PyObjC` (macOS native API bridge), `psutil` (System monitoring).
*   **Builder**: `py2app`
