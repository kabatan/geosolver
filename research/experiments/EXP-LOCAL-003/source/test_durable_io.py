from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import durable_io


class DurableIoTests(unittest.TestCase):
    def test_exclusive_write_is_complete_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "authority.json"
            durable_io.exclusive_write(path, b'{"sealed":true}')
            self.assertEqual(path.read_bytes(), b'{"sealed":true}')
            with self.assertRaises(OSError):
                durable_io.exclusive_write(path, b"replacement")
            self.assertEqual(path.read_bytes(), b'{"sealed":true}')

    def test_durable_staging_write_and_no_replace_directory_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / ".stage.partial"
            staging.mkdir()
            nested = staging / "nested"
            nested.mkdir()
            durable_io.durable_write(nested / "payload.bin", b"payload")
            destination = root / "published"
            durable_io.durable_rename_noreplace(staging, destination)
            self.assertFalse(staging.exists())
            self.assertEqual(
                (destination / "nested" / "payload.bin").read_bytes(), b"payload"
            )

            second = root / ".second.partial"
            second.mkdir()
            durable_io.durable_write(second / "other.bin", b"other")
            with self.assertRaises(OSError):
                durable_io.durable_rename_noreplace(second, destination)
            self.assertTrue(second.is_dir())
            self.assertEqual(
                (destination / "nested" / "payload.bin").read_bytes(), b"payload"
            )


if __name__ == "__main__":
    unittest.main()
