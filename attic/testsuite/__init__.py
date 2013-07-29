import filecmp
import os
import posix
import sys
import sysconfig
import time
import unittest
from attic.helpers import st_mtime_ns
from attic.xattr import get_all

# The mtime get/set precison varies on different OS and Python versions
if 'HAVE_FUTIMENS' in posix._have_functions:
    st_mtime_ns_round = 0
elif 'HAVE_UTIMES' in sysconfig.get_config_vars():
    st_mtime_ns_round = -3
else:
    st_mtime_ns_round = -9


has_mtime_ns = sys.version >= '3.3'
utime_supports_fd = os.utime in getattr(os, 'supports_fd', {})


class AtticTestCase(unittest.TestCase):
    """
    """
    assert_equal = unittest.TestCase.assertEqual
    assert_not_equal = unittest.TestCase.assertNotEqual
    assert_raises = unittest.TestCase.assertRaises

    def _get_xattrs(self, path):
        try:
            return get_all(path, follow_symlinks=False)
        except EnvironmentError:
            return {}

    def assert_dirs_equal(self, dir1, dir2, fuse=False):
        diff = filecmp.dircmp(dir1, dir2)
        self._assert_dirs_equal_cmp(diff, fuse)

    def _assert_dirs_equal_cmp(self, diff, fuse=False):
        self.assert_equal(diff.left_only, [])
        self.assert_equal(diff.right_only, [])
        self.assert_equal(diff.diff_files, [])
        self.assert_equal(diff.funny_files, [])
        for filename in diff.common:
            path1 = os.path.join(diff.left, filename)
            path2 = os.path.join(diff.right, filename)
            s1 = os.lstat(path1)
            s2 = os.lstat(path2)
            attrs = ['st_mode', 'st_uid', 'st_gid', 'st_rdev']
            if not fuse or not os.path.isdir(path1):
                # dir nlink is always 1 on our fuse fileystem
                attrs.append('st_nlink')
            d1 = [filename] + [getattr(s1, a) for a in attrs]
            d2 = [filename] + [getattr(s2, a) for a in attrs]
            if not os.path.islink(path1) or utime_supports_fd:
                # llfuse does not provide ns precision for now
                if fuse:
                    d1.append(round(st_mtime_ns(s1), -4))
                    d2.append(round(st_mtime_ns(s2), -4))
                else:
                    d1.append(round(st_mtime_ns(s1), st_mtime_ns_round))
                    d2.append(round(st_mtime_ns(s2), st_mtime_ns_round))
            d1.append(self._get_xattrs(path1))
            d2.append(self._get_xattrs(path2))
            self.assert_equal(d1, d2)
        for sub_diff in diff.subdirs.values():
            self._assert_dirs_equal_cmp(sub_diff, fuse)

    def wait_for_mount(self, path, timeout=5):
        """Wait until a filesystem is mounted on `path`
        """
        timeout += time.time()
        while timeout > time.time():
            if os.path.ismount(path):
                return
            time.sleep(.1)
        raise Exception('wait_for_mount(%s) timeout' % path)


def get_tests(suite):
    """Generates a sequence of tests from a test suite
    """
    for item in suite:
        try:
            # TODO: This could be "yield from..." with Python 3.3+ 
            for i in get_tests(item):
                yield i
        except TypeError:
            yield item


class TestLoader(unittest.TestLoader):
    """A customzied test loader that properly detects and filters our test cases
    """

    def loadTestsFromName(self, pattern, module=None):
        suite = self.discover('attic.testsuite', '*.py')
        tests = unittest.TestSuite()
        for test in get_tests(suite):
            if pattern.lower() in test.id().lower():
                tests.addTest(test)
        return tests

