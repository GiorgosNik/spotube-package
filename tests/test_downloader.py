import unittest
from src.spotube.downloader import downloader

# Testing API KEYS
SPOTIFY_ID = "ff55dcadd44e4cb0819ebe5be80ab687"
SPOTIFY_SECRET = "5539f7392ae94dd5b3dfc1d57381303a"
GENIUS_TOKEN = "5dRV7gMtFLgnlF632ZzqZutSsvPC0IWyFUJ1W8pWHj185RAMFgR4FtX76ckFDjFZ"


class TestDownloader(unittest.TestCase):
    def test_upper(self):
        test_downloader = downloader(SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN)
        self.assertNotEqual(test_downloader, None)


if __name__ == '__main__':
    unittest.main()