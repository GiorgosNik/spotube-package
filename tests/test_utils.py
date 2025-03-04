import unittest
import pytest
import os
import shutil
from spotube.dependency_handler import DependencyHandler
from unittest.mock import Mock, patch
from spotube.downloader_utils import get_lyrics
from spotube.downloader_utils import format_artists
from spotube.downloader_utils import format_artists
from spotube.downloader_utils import format_artists
from spotube.downloader_utils import format_song_data
from spotube.downloader_utils import match_target_amplitude
from pydub import AudioSegment
from spotube.downloader_utils import ensure_directory_exists
from pathlib import Path
from spotube.downloader_utils import send_message
from spotube.downloader_utils import send_message
from spotube.downloader_utils import _extract_tags
from spotube.downloader_utils import _extract_tags

@pytest.fixture(autouse=True)
def run_around_tests():
    if os.path.exists("./Test_Directory"):
        shutil.rmtree("./Test_Directory")
    yield
    if os.path.exists("./Test_Directory"):
        shutil.rmtree("./Test_Directory")


class TestUtils(unittest.TestCase):
    def test_get_lyrics_with_feature(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="These are the lyrics EmbedShare 123")
        
        result = get_lyrics("Song ft. Artist", "Artist", genius_obj)
        
        assert result == "These are the lyrics"

    def test_get_lyrics_without_feature(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="These are the lyrics EmbedShare 123")
        
        result = get_lyrics("Song", "Artist", genius_obj)
        
        assert result == "These are the lyrics"

    def test_get_lyrics_no_lyrics_found(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = None
        
        result = get_lyrics("Song", "Artist", genius_obj)
        
        assert result is None

    def test_get_lyrics_with_multiple_features(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="These are the lyrics EmbedShare 123")
        
        result = get_lyrics("Song (feat. Artist1, Artist2)", "Artist", genius_obj)
        
        assert result == "These are the lyrics"

    def test_get_lyrics_with_different_feature_formats(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="These are the lyrics EmbedShare 123")
        
        result1 = get_lyrics("Song ft. Artist", "Artist", genius_obj)
        result2 = get_lyrics("Song feat Artist", "Artist", genius_obj)
        result3 = get_lyrics("Song (feat Artist)", "Artist", genius_obj)
        result4 = get_lyrics("Song (ft. Artist)", "Artist", genius_obj)
        result5 = get_lyrics("Song (feat. Artist)", "Artist", genius_obj)
        
        assert result1 == "These are the lyrics"
        assert result2 == "These are the lyrics"
        assert result3 == "These are the lyrics"
        assert result4 == "These are the lyrics"
        assert result5 == "These are the lyrics"

    def test_format_artists(self):
        artist_list = [
            {"name": "Artist1"},
            {"name": "Artist2"},
            {"name": "Artist3"}
        ]
        result = format_artists(artist_list)
        assert result == "Artist1, Artist2, Artist3"

    def test_format_artists_single(self):
        artist_list = [{"name": "Artist1"}]
        result = format_artists(artist_list)
        assert result == "Artist1"

    def test_format_artists_empty(self):
        artist_list = []
        result = format_artists(artist_list)
        assert result == ""

    def test_format_song_data(self):
        song = {
            "track": {
                "name": "Test Song",
                "artists": [{"name": "Test Artist"}],
                "album": {
                    "name": "Test Album",
                    "release_date": "2021-01-01",
                    "images": [{"url": "test_url"}]
                },
                "duration_ms": 1000
            }
        }
        result = format_song_data(song)
        expected = {
            "name": "Test Song",
            "artist": "Test Artist", 
            "album": "Test Album",
            "year": "2021",
            "duration": 1000,
            "url": "test_url"
        }
        assert result == expected

    def test_match_target_amplitude(self):
        
        mock_sound = Mock(spec=AudioSegment)
        mock_sound.dBFS = -20.0
        mock_sound.apply_gain.return_value = "normalized_sound"
        
        result = match_target_amplitude(mock_sound, -14.0)
        
        assert result == "normalized_sound"
        mock_sound.apply_gain.assert_called_once_with(6.0)

    def test_send_message(self):
        mock_channel = Mock()
        
        send_message(mock_channel, "test_type", ["test_content"])
        
        mock_channel.put.assert_called_once_with({
            "type": "test_type", 
            "contents": ["test_content"]
        })

    def test_send_message_no_channel(self):
        # Should not raise any error when channel is None
        send_message(None, "test_type", ["test_content"])

    def test_extract_tags_with_no_tag(self):
        mock_audio = Mock()
        mock_audio.tag = None
        
        result = _extract_tags(mock_audio)
        expected = {
            "artist": "",
            "title": "",
            "album": "",
            "lyrics": "",
            "images": []
        }
        
        assert result == expected

    def test_extract_tags_with_tags(self):
        mock_audio = Mock()
        mock_audio.tag.artist = "Test Artist"
        mock_audio.tag.title = "Test Title" 
        mock_audio.tag.album = "Test Album"
        mock_audio.tag.lyrics = [Mock(text="Test Lyrics")]
        
        result = _extract_tags(mock_audio)
        expected = {
            "artist": "Test Artist",
            "title": "Test Title",
            "album": "Test Album", 
            "lyrics": "Test Lyrics",
            "images": []
        }
        
        assert result == expected

if __name__ == "__main__":
    unittest.main()
