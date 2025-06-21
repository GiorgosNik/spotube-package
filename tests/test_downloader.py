import pytest
import os
import shutil
import queue
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from spotube.download_manager import DownloadManager

@pytest.fixture(autouse=True)
def run_around_tests():
    if os.path.exists("./Test_Directory"):
        shutil.rmtree("./Test_Directory")
    yield
    if os.path.exists("./Test_Directory"):
        shutil.rmtree("./Test_Directory")


class TestDownloader:
    
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    def test_constructor(self, mock_ffmpeg, mock_auth):
        downloader = DownloadManager("test_id", "test_secret", "test_key")
        
        assert downloader.progress == 0
        assert downloader.working == False
        assert downloader.total == 0
        assert downloader.current_song is None
        assert downloader.eta is None
        mock_auth.assert_called_once_with("test_id", "test_secret", "test_key")
        
    def test_set_directory(self):
        with patch('spotube.download_manager.Authenticator'), \
             patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True):
            downloader = DownloadManager("test_id", "test_secret", "test_key")
            downloader.set_directory("./new_directory")
            
            assert downloader.directory == "./new_directory"
    
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    @patch('spotube.download_manager.utils.download_playlist')
    def test_start_downloader(self, mock_download, mock_ffmpeg, mock_auth):
        downloader = DownloadManager("test_id", "test_secret", "test_key")
        downloader.start_downloader("test_link")
        
        # Wait briefly for thread to start
        time.sleep(0.1)
        
        assert downloader.working == True
        assert downloader.thread is not None
        
        # Clean up
        downloader.thread.join(timeout=1.0)
    
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    def test_cancel_downloader(self, mock_ffmpeg, mock_auth):
        downloader = DownloadManager("test_id", "test_secret", "test_key")
        downloader.start_downloader("test_link")
        
        # Wait briefly for thread to start
        time.sleep(0.1)
        
        assert downloader.working == True
        assert downloader.thread is not None
        
        # Cancel the downloader
        downloader.cancel_downloader()
        
        # Wait briefly for thread to stop
        time.sleep(0.1)
        
        assert downloader.working == False
        assert downloader.thread is None
    
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    def test_update_progress(self, mock_ffmpeg, mock_auth):
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
            normalized_songs=2
        )
        
        assert downloader.progress == 5
        assert downloader.total == 10
        assert downloader.success_counter == 3
        assert downloader.failure_counter == 2
        assert downloader.current_song == "Test Song"
        assert downloader.eta == "15.5"
        assert downloader.working == True
        assert downloader.normalizing == True
        assert downloader.normalized_songs == 2
    
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    def test_validate_playlist_url(self, mock_ffmpeg, mock_auth):
        mock_spotify_auth = MagicMock()
        mock_auth.return_value.spotify_auth = mock_spotify_auth
        
        downloader = DownloadManager("test_id", "test_secret", "test_key")
        
        # Test valid URL
        mock_spotify_auth.playlist_items.return_value = {"items": []}
        result = downloader.validate_playlist_url("valid_url")
        assert result == True
        
        # Test invalid URL
        mock_spotify_auth.playlist_items.side_effect = Exception("Invalid URL")
        result = downloader.validate_playlist_url("invalid_url")
        assert result == False
    
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    def test_get_current_song(self, mock_ffmpeg, mock_auth):
        downloader = DownloadManager("test_id", "test_secret", "test_key")
        downloader.current_song = "Test Song by Artist"
        
        assert downloader.current_song == "Test Song by Artist"
    
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    def test_get_eta(self, mock_ffmpeg, mock_auth):
        downloader = DownloadManager("test_id", "test_secret", "test_key")
        downloader.eta = 42.5
        
        assert downloader.eta == pytest.approx(42.5)
    
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    def test_get_total(self, mock_ffmpeg, mock_auth):
        downloader = DownloadManager("test_id", "test_secret", "test_key")
        downloader.total = 100
        
        assert downloader.total == 100
    
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    def test_get_progress(self, mock_ffmpeg, mock_auth):
        downloader = DownloadManager("test_id", "test_secret", "test_key")
        downloader.progress = 42
        
        assert downloader.progress == 42
        
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    def test_get_success_counter(self, mock_ffmpeg, mock_auth):
        downloader = DownloadManager("test_id", "test_secret", "test_key")
        downloader.success_counter = 15
        
        assert downloader.success_counter == 15
        
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    def test_get_fail_counter(self, mock_ffmpeg, mock_auth):
        downloader = DownloadManager("test_id", "test_secret", "test_key")
        downloader.fail_counter = 3
        
        assert downloader.fail_counter == 3
        
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    @patch('spotube.download_manager.utils.download_playlist')
    def test_song_number_limit(self, mock_download, mock_ffmpeg, mock_auth):
        downloader = DownloadManager("test_id", "test_secret", "test_key", song_number_limit=5)
        downloader.start_downloader("test_link")
        
        # Wait briefly for thread to start
        time.sleep(0.1)
        
        assert downloader.song_number_limit == 5
        mock_download.assert_called_once()
        assert mock_download.call_args[0][5] == 5  # song_number_limit parameter
        
        # Clean up
        downloader.thread.join(timeout=1.0)
        
    @patch('spotube.download_manager.Authenticator')
    @patch('spotube.download_manager.DependencyHandler.ffmpeg_installed', return_value=True)
    def test_different_path(self, mock_ffmpeg, mock_auth):
        custom_path = "./Custom_Songs_Path"
        downloader = DownloadManager("test_id", "test_secret", "test_key", directory=custom_path)
        
        assert downloader.directory == custom_path