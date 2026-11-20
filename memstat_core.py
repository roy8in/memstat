"""Pure data-collection and grouping utilities for MemStat."""

import ctypes
import ctypes.util
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import psutil

BYTES_PER_GIB = 1024 ** 3
BYTES_PER_MIB = 1024 ** 2


@dataclass(frozen=True)
class ProcessRecord:
    """A process and its identity at the time it was sampled."""

    pid: int
    ppid: int
    name: str
    username: str
    rss: int
    created: float
    bundle_path: str = ""


@dataclass
class ProcessGroup:
    """A bundle of processes, with summed RSS (not unique RAM usage)."""

    key: str
    name: str
    bundle_path: str = ""
    records: list = field(default_factory=list)
    rss: int = 0
    app_pid: int = 0


@dataclass(frozen=True)
class MemorySnapshot:
    total: int
    used: int
    available: int
    wired: int
    swap_used: int
    pressure: str

    @property
    def used_percent(self):
        """Match the displayed 'In use' and 'Total' numbers exactly."""
        if not self.total:
            return 0.0
        return 100.0 * self.used / self.total


def format_gib(value):
    """Format byte counts with accurate binary-unit labeling."""
    return f"{value / BYTES_PER_GIB:.1f} GiB"


def format_process_memory(value):
    """Use MiB for smaller processes and GiB for large ones."""
    if value >= BYTES_PER_GIB:
        return f"{value / BYTES_PER_GIB:.1f} GiB"
    return f"{value / BYTES_PER_MIB:.0f} MiB"


def bundle_from_executable(path):
    """Return the outermost .app path, not an embedded Helper.app."""
    if not path:
        return ""
    match = re.search(r"(^|/)([^/]+\.app)(?=/|$)", path, re.IGNORECASE)
    if match is None:
        return ""
    return path[:match.end(2)]


def parse_compressor_bytes(output):
    """Parse resident compressor storage, not pre-compression page count."""
    page = re.search(r"page size of\s+(\d+)\s+bytes", output)
    occupied = re.search(
        r"Pages occupied by compressor:\s*([\d,]+)\.?", output
    )
    if not page or not occupied:
        return None
    return int(page.group(1)) * int(occupied.group(1).replace(",", ""))


def get_compressor_bytes():
    """Return None instead of wrongly reporting zero on vm_stat failure."""
    if sys.platform != "darwin":
        return None
    try:
        output = subprocess.check_output(
            ["/usr/bin/vm_stat"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=0.7,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_compressor_bytes(output)


def read_memory_pressure():
    """Read macOS's discrete pressure signal when the sysctl is available.

    The sysctl is undocumented and can disappear on future macOS versions.
    Unknown results must be reported as unavailable, not as 'Normal'.
    """
    if sys.platform != "darwin":
        return "Unavailable"
    try:
        library = ctypes.util.find_library("c")
        if not library:
            return "Unavailable"
        libc = ctypes.CDLL(library, use_errno=True)
        sysctl = libc.sysctlbyname
        sysctl.argtypes = [
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        sysctl.restype = ctypes.c_int
        level = ctypes.c_int32()
        size = ctypes.c_size_t(ctypes.sizeof(level))
        result = sysctl(
            b"kern.memorystatus_vm_pressure_level",
            ctypes.byref(level),
            ctypes.byref(size),
            None,
            0,
        )
        if result != 0 or size.value != ctypes.sizeof(level):
            return "Unavailable"
        return {1: "Normal", 2: "Warning", 4: "Critical"}.get(
            level.value, "Unavailable"
        )
    except (AttributeError, OSError, TypeError, ValueError):
        return "Unavailable"


def sample_memory():
    """Sample system memory without running external processes."""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return MemorySnapshot(
        total=mem.total,
        used=mem.used,
        available=mem.available,
        wired=getattr(mem, "wired", 0),
        swap_used=swap.used,
        pressure=read_memory_pressure(),
    )


def sample_processes(username, excluded_pid=None):
    """Collect only processes owned by the current account."""
    attributes = [
        "pid", "ppid", "name", "username", "memory_info",
        "create_time", "exe",
    ]
    records = []
    for process in psutil.process_iter(attributes, ad_value=None):
        try:
            data = process.info
            if data["username"] != username:
                continue
            if data["pid"] == excluded_pid:
                continue
            memory = data["memory_info"]
            if memory is None or data["create_time"] is None:
                continue
            records.append(ProcessRecord(
                pid=data["pid"],
                ppid=data["ppid"] or 0,
                name=data["name"] or f"PID {data['pid']}",
                username=data["username"],
                rss=memory.rss,
                created=data["create_time"],
                bundle_path=bundle_from_executable(data["exe"]),
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied,
                psutil.ZombieProcess):
            continue
    return records


def group_processes(records, running_apps=None):
    """Group by real outer .app bundle, then by a bundled ancestor.

    Other processes stay separate; matching names alone are not identity.
    running_apps: {bundle_path: (application_name, application_pid)}
    """
    running_apps = running_apps or {}
    by_pid = {record.pid: record for record in records}
    groups = {}

    for record in records:
        bundle = record.bundle_path
        ancestor = record
        seen = {record.pid}
        while not bundle and ancestor.ppid in by_pid:
            if ancestor.ppid in seen:
                break
            seen.add(ancestor.ppid)
            ancestor = by_pid[ancestor.ppid]
            bundle = ancestor.bundle_path

        if bundle:
            key = "app:" + bundle
            default_name = Path(bundle).name[:-4]
            app_name, app_pid = running_apps.get(
                bundle, (default_name, 0)
            )
        else:
            key = f"process:{record.pid}:{record.created}"
            app_name, app_pid = record.name, 0

        if key not in groups:
            groups[key] = ProcessGroup(
                key=key,
                name=app_name,
                bundle_path=bundle,
                app_pid=app_pid,
            )
        group = groups[key]
        group.records.append(record)
        group.rss += record.rss

    for group in groups.values():
        group.records.sort(key=lambda item: item.rss, reverse=True)
    return sorted(groups.values(), key=lambda item: item.rss, reverse=True)


def process_identity_matches(process, record, username):
    """Guard against PID reuse or a switch to another account."""
    try:
        return (
            process.pid == record.pid
            and abs(process.create_time() - record.created) < 0.01
            and process.username() == username
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied,
            psutil.ZombieProcess):
        return False