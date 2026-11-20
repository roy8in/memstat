"""Cross-platform tests for Mac-independent MemStat logic."""

import unittest
from collections import namedtuple
from unittest.mock import Mock, patch

from memstat_core import (
    BYTES_PER_GIB,
    MemorySnapshot,
    ProcessRecord,
    bundle_from_executable,
    format_process_memory,
    group_processes,
    parse_compressor_bytes,
    process_identity_matches,
    sample_processes,
)


class MemoryTests(unittest.TestCase):
    def test_used_percent_uses_displayed_used_value(self):
        snapshot = MemorySnapshot(
            total=24 * BYTES_PER_GIB,
            used=9 * BYTES_PER_GIB,
            available=12 * BYTES_PER_GIB,
            wired=0,
            swap_used=0,
            pressure="Normal",
        )
        self.assertEqual(snapshot.used_percent, 37.5)

    def test_zero_total(self):
        snapshot = MemorySnapshot(0, 0, 0, 0, 0, "Unavailable")
        self.assertEqual(snapshot.used_percent, 0.0)

    def test_compressor_parser(self):
        output = (
            'Mach Virtual Memory Statistics: (page size of 16384 bytes)\n'
            'Pages stored in compressor: 999.\n'
            'Pages occupied by compressor: 12,345.\n'
        )
        self.assertEqual(parse_compressor_bytes(output), 12345 * 16384)
        self.assertIsNone(parse_compressor_bytes('No information'))

    def test_binary_units(self):
        self.assertEqual(format_process_memory(BYTES_PER_GIB), '1.0 GiB')


class GroupingTests(unittest.TestCase):
    @staticmethod
    def make_record(pid, ppid, name, rss, bundle="", created=1.0):
        return ProcessRecord(
            pid, ppid, name, "user", rss, created, bundle
        )

    def test_executable_path_picks_outer_app_bundle(self):
        path = (
            '/Applications/Google Chrome.app/Contents/Frameworks/'
            'Google Chrome Helper.app/Contents/MacOS/Helper'
        )
        self.assertEqual(
            bundle_from_executable(path), '/Applications/Google Chrome.app'
        )

    def test_bundle_groups_chrome_helper_and_parentless_helper(self):
        bundle = '/Applications/Google Chrome.app'
        records = [
            self.make_record(10, 1, 'Google Chrome', 100, bundle),
            self.make_record(11, 10, 'Google Chrome Helper', 200),
            self.make_record(12, 1, 'Google Chrome Helper', 300, bundle),
        ]
        groups = group_processes(records, {bundle: ('Google Chrome', 10)})
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].rss, 600)
        self.assertEqual(groups[0].app_pid, 10)
        self.assertEqual(len(groups[0].records), 3)

    def test_unrelated_same_named_processes_do_not_merge(self):
        records = [
            self.make_record(1, 0, 'Worker', 250),
            self.make_record(2, 0, 'Worker', 200),
        ]
        self.assertEqual(len(group_processes(records)), 2)

    def test_cyclic_ppid_terminates(self):
        records = [
            self.make_record(1, 2, 'A', 100),
            self.make_record(2, 1, 'B', 200),
        ]
        self.assertEqual(len(group_processes(records)), 2)

    def test_identity_rejects_reused_pid(self):
        record = self.make_record(10, 1, 'Chrome', 100, created=1.0)
        process = Mock(pid=10)
        process.create_time.return_value = 2.0
        process.username.return_value = 'user'
        self.assertFalse(process_identity_matches(process, record, 'user'))

    def test_identity_accepts_matching_pid_and_start_time(self):
        record = self.make_record(10, 1, 'Chrome', 100, created=1.0)
        process = Mock(pid=10)
        process.create_time.return_value = 1.0
        process.username.return_value = 'user'
        self.assertTrue(process_identity_matches(process, record, 'user'))

    def test_user_filter_and_self_exclusion(self):
        memory = namedtuple('Mem', 'rss')(100)
        sample = {
            'pid': 8, 'ppid': 1, 'name': 'Other', 'username': 'user',
            'memory_info': memory, 'create_time': 100.0, 'exe': None,
        }
        other = dict(sample, pid=10, username='somebody-else')
        own = dict(sample, pid=11, name='MemStat')
        processes = [Mock(info=sample), Mock(info=other), Mock(info=own)]
        with patch('memstat_core.psutil.process_iter', return_value=processes):
            records = sample_processes('user', excluded_pid=11)
        self.assertEqual([record.pid for record in records], [8])


if __name__ == '__main__':
    unittest.main()