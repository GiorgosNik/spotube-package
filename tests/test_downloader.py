import unittest
import pytest
import time
import os
import shutil
from src.spotube.downloader_class import downloader
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
        test_downloader = downloader(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )
        self.assertNotEqual(test_downloader, None)

    def test_set_directory(self):
        test_downloader = downloader(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )
        test_downloader.set_directory("./test")
        self.assertEqual(test_downloader.directory, "./test")

    def test_validate_playlist_url(self):
        test_downloader = downloader(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        playlist_validity = test_downloader.validate_playlist_url(VALID_PLAYLIST)
        self.assertEqual(playlist_validity, True)

        playlist_validity = test_downloader.validate_playlist_url(INVALID_PLAYLIST)
        self.assertEqual(playlist_validity, False)

    def test_get_total(self):
        test_downloader = downloader(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        total = test_downloader.get_total()
        self.assertEqual(total, None)

    def test_get_progress(self):
        test_downloader = downloader(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        progress = test_downloader.get_progress()
        self.assertEqual(progress, 0)

    def test_get_current_song(self):
        test_downloader = downloader(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        current_song = test_downloader.get_current_song()
        self.assertEqual(current_song, None)

    def test_get_eta(self):
        test_downloader = downloader(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        eta = test_downloader.get_eta()
        self.assertEqual(eta, None)

    def test_start_downloader(self):
        test_downloader = downloader(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        test_downloader.start_downloader(VALID_PLAYLIST)

        while test_downloader.is_working():
            time.sleep(1)

        self.assertTrue(
            os.path.exists("./Test_Directory/TRAP.mp3")
            and os.path.exists("./Test_Directory/C'est pas d'ma faute c'est l'mood.mp3")
        )

    def test_stop_downloader(self):
        test_downloader = downloader(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Test_Directory"
        )

        test_downloader.start_downloader(VALID_PLAYLIST)
        test_downloader.stop_downloader()

        while test_downloader.is_working():
            time.sleep(1)

        self.assertTrue(
            os.path.exists("./Test_Directory/C'est pas d'ma faute c'est l'mood.mp3")
            and not os.path.exists("./Test_Directory/TRAP.mp3")
        )


if __name__ == "__main__":
    unittest.main()
