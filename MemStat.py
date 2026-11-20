"""Native-looking macOS memory monitor in the menu bar."""

import getpass
import logging
import os
import subprocess
import threading

import objc
import psutil
import rumps
from AppKit import (
    NSAttributedString,
    NSFont,
    NSFontAttributeName,
    NSImage,
    NSImageLeft,
    NSObject,
    NSParagraphStyleAttributeName,
    NSRightTextAlignment,
    NSTextTab,
    NSMutableParagraphStyle,
    NSWorkspace,
)
from PyObjCTools import AppHelper

from memstat_core import (
    format_gib,
    format_process_memory,
    get_compressor_bytes,
    group_processes,
    process_identity_matches,
    sample_memory,
    sample_processes,
)

LOG = logging.getLogger(__name__)
TOP_GROUP_COUNT = 7
MORE_GROUP_COUNT = 20
TOP_PROCESS_COUNT = 15
PROTECTED_NAMES = frozenset({
    "launchd", "loginwindow", "WindowServer", "kernel_task", "MemStat",
})


class MenuDelegate(NSObject):
    """Keep the menu stable while it is being used."""

    def initWithApp_(self, app):
        self = objc.super(MenuDelegate, self).init()
        if self is not None:
            self.app = app
        return self

    def menuWillOpen_(self, menu):
        self.app.on_menu_open()

    def menuDidClose_(self, menu):
        self.app.on_menu_close()


class MemStatApp(rumps.App):
    def __init__(self):
        super().__init__("MemStat", title="—", quit_button=None)
        self.username = getpass.getuser()
        self.is_menu_open = False
        self.delegate_set = False
        self.menu_generation = 0
        self._status_symbol = None
        self._sample_inflight = False
        self._compressor_inflight = False
        self._group_rows = []
        self._process_rows = []
        self._process_by_pid = {}
        self._summary_rows = {}
        self.menu.add(rumps.MenuItem("MemStat is starting…"))
        self.menu.add(rumps.MenuItem(
            "Quit MemStat", callback=rumps.quit_application
        ))

    @rumps.timer(2)
    def update_status_timer(self, _):
        if not self.delegate_set and hasattr(self, "_nsapp"):
            self._attach_menu_delegate()
        try:
            memory = sample_memory()
            percent = memory.used_percent
            if hasattr(self, "_nsapp"):
                button = self._nsapp.nsstatusitem.button()
                button.setTitle_(f"{percent:.0f}%")
                if self._status_symbol is not None:
                    button.setImage_(self._status_symbol)
                button.setImagePosition_(NSImageLeft)
                button.setFont_(
                    NSFont.monospacedDigitSystemFontOfSize_weight_(12.0, 0.0)
                )
            else:
                self.title = f"{percent:.0f}%"
            if self.is_menu_open:
                self._update_summary(memory)
        except (OSError, AttributeError, ValueError):
            LOG.exception("Unable to refresh memory status")

    @rumps.timer(5)
    def update_open_menu_timer(self, _):
        if not self.is_menu_open:
            return
        self._request_process_sample()
        self._request_compressor_sample()

    def _attach_menu_delegate(self):
        try:
            self.delegate = MenuDelegate.alloc().initWithApp_(self)
            self._nsapp.nsstatusitem.menu().setDelegate_(self.delegate)
            self.delegate_set = True
            self._rebuild_menu()
        except (AttributeError, ValueError):
            LOG.exception("Could not attach native menu delegate")
            self._rebuild_menu()
            return
        try:
            symbol = (
                NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                    "memorychip", "Memory usage"
                )
            )
            if symbol is not None:
                symbol.setTemplate_(True)
                self._status_symbol = symbol
        except (AttributeError, ValueError):
            # SF Symbols are not available on macOS 10.15.
            LOG.info("Using percentage-only status item")

    def on_menu_open(self):
        self.is_menu_open = True
        self._rebuild_menu()
        self._request_compressor_sample()

    def on_menu_close(self):
        self.is_menu_open = False
        self.menu_generation += 1

    @staticmethod
    def _make_item(label, callback=None, bold=False):
        item = rumps.MenuItem(label, callback=callback)
        if bold:
            font = NSFont.boldSystemFontOfSize_(12.5)
            attributes = {NSFontAttributeName: font}
            title = NSAttributedString.alloc().initWithString_attributes_(
                label, attributes
            )
            item._menuitem.setAttributedTitle_(title)
        return item

    @staticmethod
    def _set_two_column(item, label, value, emphasis=False):
        """Align values without relying on spaces in proportional fonts."""
        content = f"{label}\t{value}"
        paragraph = NSMutableParagraphStyle.alloc().init()
        tab = NSTextTab.alloc().initWithTextAlignment_location_options_(
            NSRightTextAlignment, 254, {}
        )
        paragraph.setTabStops_([tab])
        text_font = (NSFont.boldSystemFontOfSize_(12.5) if emphasis
                     else NSFont.menuFontOfSize_(13.0))
        attributes = {
            NSFontAttributeName: text_font,
            NSParagraphStyleAttributeName: paragraph,
        }
        title = NSAttributedString.alloc().initWithString_attributes_(
            content, attributes
        ).mutableCopy()
        digit_font = NSFont.monospacedDigitSystemFontOfSize_weight_(
            12.5, 0.0
        )
        offset = len((label + "\t").encode("utf-16-le")) // 2
        length = len(value.encode("utf-16-le")) // 2
        title.addAttribute_value_range_(
            NSFontAttributeName, digit_font, (offset, length)
        )
        item._menuitem.setAttributedTitle_(title)

    def _add_summary(self, label, value, key=None, emphasis=False):
        item = self._make_item(label)
        self._set_two_column(item, label, value, emphasis=emphasis)
        self.menu.add(item)
        if key is not None:
            self._summary_rows[key] = (item, label, emphasis)
        return item

    @staticmethod
    def _truncate(text, maximum=26):
        return text if len(text) <= maximum else text[:maximum - 1] + "…"

    def _get_running_apps(self):
        """Use macOS application identities, not a guessed name prefix."""
        running = {}
        try:
            for app in NSWorkspace.sharedWorkspace().runningApplications():
                bundle_url = app.bundleURL()
                if bundle_url is None:
                    continue
                path = str(bundle_url.path())
                if not path:
                    continue
                name = str(app.localizedName() or "")
                running[path] = (name or path.rsplit("/", 1)[-1][:-4],
                                 int(app.processIdentifier()))
        except (AttributeError, ValueError):
            LOG.exception("Application metadata is unavailable")
        return running

    def _rebuild_menu(self):
        """Only rebuild before opening, never while navigating an open menu."""
        self.menu_generation += 1
        self.menu.clear()
        self._group_rows = []
        self._process_rows = []
        self._summary_rows = {}
        try:
            memory = sample_memory()
        except (OSError, psutil.Error):
            LOG.exception("Could not read system memory")
            memory = None

        if memory is not None:
            self._add_summary(
                "Memory", f"{format_gib(memory.used)} / "
                f"{format_gib(memory.total)}", "memory", emphasis=True
            )
            self._add_summary(
                "Memory Pressure", memory.pressure, "pressure"
            )
            self.menu.add(rumps.separator)
            self._add_summary(
                "Available", format_gib(memory.available), "available"
            )
            self._add_summary("Wired", format_gib(memory.wired), "wired")
            self._add_summary("Compressed", "—", "compressed")
            self._add_summary(
                "Swap Used", format_gib(memory.swap_used), "swap"
            )
        else:
            self.menu.add(self._make_item("Memory information unavailable"))

        self.menu.add(rumps.separator)
        self.menu.add(self._make_item(
            "TOP APPLICATIONS  ·  SUMMED RSS", bold=True
        ))

        try:
            records = sample_processes(self.username, os.getpid())
            groups = group_processes(records, self._get_running_apps())
        except (OSError, psutil.Error):
            LOG.exception("Could not enumerate processes")
            records, groups = [], []
        self._process_by_pid = {record.pid: record for record in records}

        for group in groups[:TOP_GROUP_COUNT]:
            self._add_group_item(self.menu, group)

        remaining = groups[TOP_GROUP_COUNT:
                           TOP_GROUP_COUNT + MORE_GROUP_COUNT]
        if remaining:
            more_item = self._make_item("More Applications & Processes")
            for group in remaining:
                self._add_group_item(more_item, group)
            self.menu.add(more_item)

        if not groups:
            self.menu.add(self._make_item("No accessible processes"))
        elif len(groups) > TOP_GROUP_COUNT + MORE_GROUP_COUNT:
            count = len(groups) - TOP_GROUP_COUNT - MORE_GROUP_COUNT
            self.menu.add(self._make_item(
                f"{count} other groups (open Activity Monitor)",
                callback=self._open_activity_monitor,
            ))

        self.menu.add(rumps.separator)
        self.menu.add(self._make_item(
            "Open Activity Monitor", callback=self._open_activity_monitor
        ))
        self.menu.add(self._make_item(
            "Quit MemStat", callback=rumps.quit_application
        ))

    def _add_group_item(self, parent, group):
        name = self._truncate(group.name)
        value = format_process_memory(group.rss)
        item = self._make_item(name)
        self._set_two_column(item, name, value)
        item._menuitem.setToolTip_(
            f"{group.name}: sum of process RSS; shared memory may be "
            "counted more than once"
        )
        if group.bundle_path:
            try:
                icon = NSWorkspace.sharedWorkspace().iconForFile_(
                    group.bundle_path
                )
                if icon is not None:
                    icon.setSize_((16, 16))
                    item._menuitem.setImage_(icon)
            except (OSError, AttributeError):
                LOG.debug("No icon available for %s", group.bundle_path)

        item.add(self._make_item(
            f"{group.name}  ·  {len(group.records)} processes",
            bold=True,
        ))
        item.add(self._make_item(
            f"Summed RSS: {format_process_memory(group.rss)}"
        ))
        item.add(rumps.separator)
        for record in group.records[:TOP_PROCESS_COUNT]:
            self._add_process_item(item, record)
        if len(group.records) > TOP_PROCESS_COUNT:
            remaining = len(group.records) - TOP_PROCESS_COUNT
            item.add(self._make_item(
                f"{remaining} more processes — see Activity Monitor",
                callback=self._open_activity_monitor,
            ))

        if group.app_pid in self._process_by_pid:
            item.add(rumps.separator)
            quit_item = self._make_item(
                "Quit Application…", callback=self._request_app_quit
            )
            quit_item.process_record = self._process_by_pid[group.app_pid]
            quit_item.app_name = group.name
            item.add(quit_item)

        parent.add(item)
        self._group_rows.append((group, item, name))

    def _add_process_item(self, parent, record):
        label = self._truncate(record.name, 24)
        item = self._make_item(label)
        self._set_two_column(
            item, label, format_process_memory(record.rss)
        )
        item._menuitem.setToolTip_(
            f"{record.name} (PID {record.pid})\nRSS: "
            f"{format_process_memory(record.rss)}"
        )
        item.add(self._make_item(record.name))
        item.add(self._make_item(f"PID: {record.pid}"))
        item.add(self._make_item(
            f"RSS: {format_process_memory(record.rss)}"
        ))
        item.add(rumps.separator)
        terminate = self._make_item(
            "Terminate Process…", callback=self._request_termination
        )
        terminate.process_record = record
        item.add(terminate)
        parent.add(item)
        self._process_rows.append((record, item, label))

    def _update_summary(self, memory):
        updates = {
            "memory": f"{format_gib(memory.used)} / "
                      f"{format_gib(memory.total)}",
            "pressure": memory.pressure,
            "available": format_gib(memory.available),
            "wired": format_gib(memory.wired),
            "swap": format_gib(memory.swap_used),
        }
        for key, value in updates.items():
            if key not in self._summary_rows:
                continue
            item, label, emphasis = self._summary_rows[key]
            self._set_two_column(item, label, value, emphasis)

    def _request_compressor_sample(self):
        if self._compressor_inflight:
            return
        self._compressor_inflight = True
        generation = self.menu_generation

        def worker():
            try:
                value = get_compressor_bytes()
            except Exception:
                LOG.exception("Compressor query failed")
                value = None
            AppHelper.callAfter(self._show_compressor, generation, value)

        threading.Thread(target=worker, daemon=True).start()

    def _show_compressor(self, generation, compressed):
        self._compressor_inflight = False
        if not self.is_menu_open or generation != self.menu_generation:
            return
        if "compressed" in self._summary_rows:
            item, label, _ = self._summary_rows["compressed"]
            value = format_gib(compressed) if compressed is not None else "—"
            self._set_two_column(item, label, value)

    def _request_process_sample(self):
        if self._sample_inflight:
            return
        self._sample_inflight = True
        generation = self.menu_generation

        def worker():
            try:
                processes = sample_processes(self.username, os.getpid())
            except Exception:
                LOG.exception("Background process sample failed")
                processes = None
            AppHelper.callAfter(self._update_process_values,
                                generation, processes)

        threading.Thread(target=worker, daemon=True).start()

    def _update_process_values(self, generation, processes):
        self._sample_inflight = False
        if not self.is_menu_open or generation != self.menu_generation:
            return
        if processes is None:
            return
        latest = {record.pid: record for record in processes}
        for original, item, label in self._process_rows:
            current = latest.get(original.pid)
            if current is None or abs(
                    current.created - original.created) >= 0.01:
                item._menuitem.setEnabled_(False)
                self._set_two_column(item, label, "Exited")
            else:
                self._set_two_column(
                    item, label, format_process_memory(current.rss)
                )
        for group, item, name in self._group_rows:
            total = 0
            for original in group.records:
                current = latest.get(original.pid)
                if current and abs(
                        current.created - original.created) < 0.01:
                    total += current.rss
            self._set_two_column(item, name, format_process_memory(total))

    def _check_safe_process(self, record):
        if record.pid == os.getpid() or record.name in PROTECTED_NAMES:
            rumps.alert("Protected Process", "This process cannot be "
                        "terminated from MemStat.")
            return None
        try:
            process = psutil.Process(record.pid)
            if not process_identity_matches(
                    process, record, self.username):
                rumps.alert("Process Changed", "The original process "
                            "is no longer running. Reopen the menu.")
                return None
            return process
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            rumps.alert("Process Unavailable", "Reopen the menu to refresh.")
            return None

    def _request_termination(self, sender):
        record = sender.process_record
        process = self._check_safe_process(record)
        if process is None:
            return
        response = rumps.alert(
            title="Terminate Process",
            message=(f"Terminate {record.name} (PID {record.pid})?\n"
                     "Unsaved changes may be lost."),
            ok="Terminate",
            cancel="Cancel",
        )
        if response != 1:
            return
        if not process_identity_matches(process, record, self.username):
            rumps.alert("Process Changed", "The process changed while "
                        "confirmation was open. Nothing was terminated.")
            return
        try:
            process.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied) as error:
            rumps.alert("Could Not Terminate Process", str(error))
            return
        self._verify_exit_in_background(process, record.name)

    def _request_app_quit(self, sender):
        record = sender.process_record
        process = self._check_safe_process(record)
        if process is None:
            return
        response = rumps.alert(
            title="Quit Application",
            message=(f"Ask {sender.app_name} to quit?\n"
                     "Save your work before continuing."),
            ok="Quit",
            cancel="Cancel",
        )
        if response != 1:
            return
        if not process_identity_matches(process, record, self.username):
            rumps.alert("Process Changed", "The application has changed. "
                        "Reopen the menu.")
            return
        try:
            app = NSWorkspace.sharedWorkspace().runningApplications()
            matching = next(
                (item for item in app
                 if int(item.processIdentifier()) == record.pid), None
            )
            if matching is None or not matching.terminate():
                rumps.alert("Quit Not Supported", "The application did "
                            "not accept the quit request.")
                return
        except (AttributeError, ValueError):
            LOG.exception("Could not send application quit request")
            rumps.alert("Quit Failed", "Could not request application quit.")
            return
        self._verify_exit_in_background(process, sender.app_name)

    @staticmethod
    def _verify_exit_in_background(process, name):
        def worker():
            try:
                process.wait(timeout=3.0)
                title, message = "Closed", f"{name} has exited."
            except psutil.NoSuchProcess:
                title, message = "Closed", f"{name} has exited."
            except (psutil.TimeoutExpired, psutil.AccessDenied):
                title = "Still Running"
                message = f"{name} did not exit within three seconds."
            AppHelper.callAfter(
                rumps.notification, "MemStat", title, message
            )

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _open_activity_monitor(_):
        try:
            subprocess.Popen(
                ["/usr/bin/open", "-a", "Activity Monitor"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            rumps.alert("Unable to open Activity Monitor")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    MemStatApp().run()