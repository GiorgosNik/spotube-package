import unittest
import pytest
import time
import os
import shutil
from spotube.download_manager import DownloadManager
# Testing API KEYS
SPOTIFY_ID = "ff55dcadd44e4cb0819ebe5be80ab687"
SPOTIFY_SECRET = "5539f7392ae94dd5b3dfc1d57381303a"
GENIUS_TOKEN = "5dRV7gMtFLgnlF632ZzqZutSsvPC0IWyFUJ1W8pWHj185RAMFgR4FtX76ckFDjFZ"

########################################################
# The valid playlist contains:
# - C'est pas d'ma faute c'est l'mood by Chinwvr
# - TRAP by Eryn Martin
#########################################################
VALID_PLAYLIST = (
    "https://open.spotify.com/playlist/05MWSPxUUWA0d238WFvkKA?si=0edd9cedff474f88"
)
INVALID_PLAYLIST = (
    "https://open.spotify.com/playlist/3zdqcFFsbUssss8oFbEELc?si=1a7c2641ae08404c"
)


@pytest.fixture(autouse=True)
def run_around_tests():
    if os.path.exists("./Test_Directory"):
        shutil.rmtree("./Test_Directory")
    yield
    if os.path.exists("./Test_Directory"):
        shutil.rmtree("./Test_Directory")


class TestDownloader(unittest.TestCase):
    def test_constructor(self):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )
        self.assertIsNone(test_downloader)

    def test_set_directory(self):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )
        test_downloader.set_directory("./test")
        self.assertEqual(test_downloader.directory, "./test")

    def test_validate_playlist_url(self):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        playlist_validity = test_downloader.validate_playlist_url(VALID_PLAYLIST)
        self.assertTrue(playlist_validity)

        playlist_validity = test_downloader.validate_playlist_url(INVALID_PLAYLIST)
        self.assertFalse(playlist_validity)

    def test_get_total(self):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        total = test_downloader.get_total()
        self.assertEqual(total, 0)

    def test_get_progress(self):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        progress = test_downloader.get_progress()
        self.assertEqual(progress, 0)

    def test_get_current_song(self):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        current_song = test_downloader.get_current_song()
        self.assertIsNone(current_song)

    def test_get_eta(self):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        eta = test_downloader.get_eta()
        self.assertIsNone(eta)

    def test_start_downloader(self):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        test_downloader.start_downloader(VALID_PLAYLIST)

        while test_downloader.downloader_active():
            time.sleep(1)

        self.assertTrue(
            os.path.exists("./Test_Directory/TRAP.mp3")
            and os.path.exists("./Test_Directory/C'est pas d'ma faute c'est l'mood.mp3")
        )

    def test_different_path(self, capsys):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory/TEST"
        )

        test_downloader.start_downloader(VALID_PLAYLIST)

        while test_downloader.downloader_active():
            time.sleep(1)

        # Capture the stdout and stderr
        captured = capsys.readouterr()
        # Check if the specific text is in the captured stdout
        if "Sign in to confirm you’re not a bot. This helps protect our community. Learn more" in captured.out:
            pytest.xfail("Test passed due to expected message in stdout")
        else:
            # Perform your regular assertions if the message is not present
            assert os.path.exists("./Test_Directory/TEST/TRAP.mp3")
            assert os.path.exists("./Test_Directory/TEST/C'est pas d'ma faute c'est l'mood.mp3")

    def test_cancel_downloader(self):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        test_downloader.start_downloader(VALID_PLAYLIST)
        test_downloader.cancel_downloader()

        while test_downloader.downloader_active():
            time.sleep(1)

        self.assertTrue(
            not os.path.exists("./Test_Directory/C'est pas d'ma faute c'est l'mood.mp3")
            and not os.path.exists("./Test_Directory/TRAP.mp3")
        )

    def test_get_success_counter(self):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        test_downloader.start_downloader(VALID_PLAYLIST)
        success_counter = test_downloader.get_success_counter()
        self.assertEqual(success_counter, 0)

        while test_downloader.downloader_active():
            time.sleep(1)

        success_counter = test_downloader.get_success_counter()
        self.assertEqual(success_counter, 2)

    def test_get_fail_counter(self):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        test_downloader.start_downloader(VALID_PLAYLIST)
        fail_counter = test_downloader.get_fail_counter()
        self.assertEqual(fail_counter, 0)

        while test_downloader.downloader_active():
            time.sleep(1)

        fail_counter = test_downloader.get_fail_counter()
        self.assertEqual(fail_counter, 0)

    def test_song_number_limit(self):
        test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory", song_number_limit = 1
        )

        test_downloader.start_downloader(VALID_PLAYLIST)

        while test_downloader.downloader_active():
            time.sleep(1)

        total_counter = test_downloader.get_total()
        self.assertEqual(total_counter, 1)

if __name__ == "__main__":
    unittest.main()
