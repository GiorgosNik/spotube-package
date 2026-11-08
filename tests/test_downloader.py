import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from spotube import downloader_utils
from spotube.download_manager import DownloadManager


@pytest.fixture
def ffmpeg_present():
    with patch("spotube.download_manager.utils.ffmpeg_installed", return_value=True):
        yield


class TestDownloader:
    @patch("spotube.download_manager.Authenticator")
    def test_constructor(self, mock_auth):
        downloader = DownloadManager("test_id", "test_secret", "test_key")

        assert downloader.progress == 0
        assert downloader.working is False
        assert downloader.total == 0
        assert downloader.current_song is None
        assert downloader.eta is None
        assert downloader.directory == "./Songs"
        mock_auth.assert_called_once_with("test_id", "test_secret", "test_key")

    def test_constructor_needs_no_keys_and_no_ffmpeg(self):
        with patch("spotube.download_manager.utils.ffmpeg_installed", return_value=False):
            downloader = DownloadManager()

        assert downloader.authenticator.spotify_auth is None
        assert downloader.authenticator.genius_auth is None

    @patch("spotube.download_manager.Authenticator")
    @patch("spotube.download_manager.utils.download_playlist")
    def test_start_downloader(self, mock_download, mock_auth, ffmpeg_present, tmp_path):
        downloader = DownloadManager(directory=str(tmp_path), song_number_limit=5, use_exportify=False)
        downloader.start_downloader("test_link")
        downloader.thread.join(timeout=5)

        assert downloader.working is True
        args, kwargs = mock_download.call_args
        assert args[0] == "test_link"
        assert args[2] == str(tmp_path)
        assert args[5] == 5
        assert kwargs == {"use_exportify": False}

    @patch("spotube.download_manager.Authenticator")
    def test_start_downloader_without_ffmpeg_raises_clear_error(self, mock_auth):
        downloader = DownloadManager()

        with patch("spotube.download_manager.utils.ffmpeg_installed", return_value=False):
            with pytest.raises(downloader_utils.FFmpegNotFoundError, match="winget install ffmpeg"):
                downloader.start_downloader("test_link")
        assert downloader.thread is None

    @patch("spotube.download_manager.Authenticator")
    def test_cancel_downloader_stops_thread_and_keeps_existing_songs(self, mock_auth, ffmpeg_present, tmp_path):
        started = threading.Event()
        stopped = threading.Event()
        directory = tmp_path / "Songs"
        directory.mkdir()
        (directory / "Song From Last Week.mp3").write_bytes(b"keep me")
        (directory / "My Notes.txt").write_bytes(b"keep me too")

        def endless_download(*args, **kwargs):
            (directory / "Finished This Run.mp3").write_bytes(b"done")
            (directory / "cover_photo.jpg").write_bytes(b"partial")
            started.set()
            try:
                while True:
                    time.sleep(0.01)
            except SystemExit:
                time.sleep(0.2)
                (directory / "downloaded_song.webm.part").write_bytes(b"written while stopping")
                stopped.set()

        downloader = DownloadManager(directory=str(directory))
        with patch("spotube.download_manager.utils.download_playlist", side_effect=endless_download):
            downloader.start_downloader("test_link")
            assert started.wait(timeout=5)
            thread = downloader.thread
            downloader.cancel_downloader()

        assert not thread.is_alive()
        assert stopped.is_set()
        assert downloader.working is False
        assert downloader.thread is None
        assert downloader.progress == 0
        assert sorted(p.name for p in directory.iterdir()) == ["Finished This Run.mp3", "My Notes.txt", "Song From Last Week.mp3"]

    @patch("spotube.download_manager.Authenticator")
    def test_cancel_without_running_thread_is_a_no_op(self, mock_auth, tmp_path):
        downloader = DownloadManager(directory=str(tmp_path))
        downloader.cancel_downloader()

        assert tmp_path.exists()

    @patch("spotube.download_manager.Authenticator")
    def test_update_progress(self, mock_auth):
        downloader = DownloadManager("test_id", "test_secret", "test_key")

        downloader.update_progress(
            progress=5,
            total=10,
            success_counter=3,
            failure_counter=2,
            current_song="Test Song",
            eta="15.5",
            downloader_active=True,
            normalizing=True,
            normalized_songs=2,
        )

        assert downloader.progress == 5
        assert downloader.total == 10
        assert downloader.success_counter == 3
        assert downloader.failure_counter == 2
        assert downloader.current_song == "Test Song"
        assert downloader.eta == "15.5"
        assert downloader.working is True
        assert downloader.normalizing is True
        assert downloader.normalized_songs == 2

    @patch("spotube.download_manager.Authenticator")
    def test_validate_playlist_url(self, mock_auth):
        mock_spotify_auth = MagicMock()
        mock_auth.return_value.spotify_auth = mock_spotify_auth
        downloader = DownloadManager("test_id", "test_secret", "test_key")

        mock_spotify_auth.playlist_items.return_value = {"items": []}
        assert downloader.validate_playlist_url("valid_url") is True

        mock_spotify_auth.playlist_items.side_effect = Exception("Invalid URL")
        assert downloader.validate_playlist_url("invalid_url") is False
