from spotube.download_manager import DownloadManager
# Testing API KEYS
SPOTIFY_ID = "ff55dcadd44e4cb0819ebe5be80ab687"
SPOTIFY_SECRET = "5539f7392ae94dd5b3dfc1d57381303a"
GENIUS_TOKEN = "5dRV7gMtFLgnlF632ZzqZutSsvPC0IWyFUJ1W8pWHj185RAMFgR4FtX76ckFDjFZ"


VALID_PLAYLIST = (
    "https://open.spotify.com/playlist/05MWSPxUUWA0d238WFvkKA?si=0edd9cedff474f88"
)
test_downloader = DownloadManager(
            SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory="./Songs"
        )
test_downloader.start_downloader(VALID_PLAYLIST)
