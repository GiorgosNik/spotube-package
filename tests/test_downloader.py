import unittest
from src.spotube.downloader import downloader

# Testing API KEYS
SPOTIFY_ID = "ff55dcadd44e4cb0819ebe5be80ab687"
SPOTIFY_SECRET = "5539f7392ae94dd5b3dfc1d57381303a"
GENIUS_TOKEN = "5dRV7gMtFLgnlF632ZzqZutSsvPC0IWyFUJ1W8pWHj185RAMFgR4FtX76ckFDjFZ"

VALID_PLAYLIST= "https://open.spotify.com/playlist/1jgaUl1FGzK76PPEn6i43f?si=f5b622467318460d"
INVALID_PLAYLIST = "https://open.spotify.com/playlist/3zdqcFFsbUssss8oFbEELc?si=1a7c2641ae08404c"


class TestDownloader(unittest.TestCase):
    def test_constructor(self):
        test_downloader = downloader(SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN)
        self.assertNotEqual(test_downloader, None)

    def test_set_directory(self):
        test_downloader = downloader(SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN)
        test_downloader.set_directory("./test")
        self.assertEqual(test_downloader.directory, "./test")

    def test_validate_playlist_url(self):
        test_downloader = downloader(SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN)

        playlist_validity = test_downloader.validate_playlist_url(VALID_PLAYLIST)
        self.assertEqual(playlist_validity, True)

        playlist_validity = test_downloader.validate_playlist_url(INVALID_PLAYLIST)
        self.assertEqual(playlist_validity, False)

    def test_get_total(self):
        test_downloader = downloader(SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN)

        total = test_downloader.get_total()
        self.assertEqual(total, None)

    def test_get_progress(self):
        test_downloader = downloader(SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN)

        progress = test_downloader.get_progress()
        self.assertEqual(progress, 0)

    def test_get_current_song(self):
        test_downloader = downloader(SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN)

        current_song = test_downloader.get_current_song()
        self.assertEqual(current_song, None)

    def test_get_eta(self):
        test_downloader = downloader(SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN)

        eta = test_downloader.get_eta()
        self.assertEqual(eta, None)

if __name__ == '__main__':
    unittest.main()