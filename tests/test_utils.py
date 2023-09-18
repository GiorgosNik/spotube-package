import unittest
import pytest
import os
import shutil
from spotube_package.dependency_handler import DependencyHandler
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
        DependencyHandler.download_ffmpeg("nt")
        self.assertTrue(
            os.path.exists("./ffmpeg.exe")
            and os.path.exists("./ffprobe.exe")
            and os.path.exists("./ffplay.exe")
        )
        DependencyHandler.download_ffmpeg("posix")
        self.assertTrue(
            os.path.exists("./ffmpeg")
            and os.path.exists("./ffprobe")
            and os.path.exists("./ffplay")
        )
        with pytest.raises(ValueError):
            DependencyHandler.download_ffmpeg("This will raise an exception")

if __name__ == "__main__":
    unittest.main()
