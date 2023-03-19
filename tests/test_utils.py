import unittest
import pytest
import time
import os
import shutil
from spotube_package.downloader_utils import download_ffmpeg, get_os_name

# Testing API KEYS


@pytest.fixture(autouse=True)
def run_around_tests():
    if os.path.exists("./Test_Directory"):
        shutil.rmtree("./Test_Directory")
    yield
    if os.path.exists("./Test_Directory"):
        shutil.rmtree("./Test_Directory")


class TestUtils(unittest.TestCase):
    def test_download_ffmpeg(self):
        download_ffmpeg("nt")
        self.assertTrue(
            os.path.exists("./ffmpeg.exe")
            and os.path.exists("./ffprobe.exe")
            and os.path.exists("./ffplay.exe")
        )
        download_ffmpeg("posix")
        self.assertTrue(
            os.path.exists("./ffmpeg")
            and os.path.exists("./ffprobe")
            and os.path.exists("./ffplay")
        )
        with pytest.raises(ValueError):
            download_ffmpeg("This will raise and exception")

    def test_get_os_name(self):
        os_name = get_os_name()
        if os.name == "nt":
            self.assertEqual(os_name, "nt")
        if os.name == "posix":
            self.assertEqual(os_name, "posix")


if __name__ == "__main__":
    unittest.main()
