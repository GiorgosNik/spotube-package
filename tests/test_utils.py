import unittest
import pytest
import os
import shutil
from unittest.mock import Mock
from spotube.downloader_utils import get_lyrics
from spotube.downloader_utils import format_artists
from spotube.downloader_utils import format_song_data
from spotube.downloader_utils import match_target_amplitude
from pydub import AudioSegment
from spotube.downloader_utils import send_message
from spotube.downloader_utils import _extract_tags
from spotube.downloader_utils import normalize_volume_levels
from spotube.downloader_utils import set_tags
import unittest
from unittest.mock import Mock, patch
import os

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
    
    def test_normalize_volume_levels(self):
        # Create test directory
        test_dir = "./Test_Directory"
        os.makedirs(test_dir, exist_ok=True)
        
        # Mock dependencies
        mock_audio_segment = Mock(spec=AudioSegment)
        mock_audio_segment.dBFS = -20.0
        mock_audio_segment.export.return_value = None
        
        # Create a patch for AudioSegment.from_file to return our mock
        with unittest.mock.patch('spotube.downloader_utils.AudioSegment.from_file', 
                                return_value=mock_audio_segment), \
             unittest.mock.patch('spotube.downloader_utils.match_target_amplitude', 
                               return_value=mock_audio_segment), \
             unittest.mock.patch('spotube.downloader_utils._extract_tags', 
                               return_value={"artist": "Test", "title": "Song", "album": "Album", "lyrics": "", "images": []}), \
             unittest.mock.patch('spotube.downloader_utils._restore_audio_tags'), \
             unittest.mock.patch('spotube.downloader_utils._save_images'), \
             unittest.mock.patch('spotube.downloader_utils.DependencyHandler.ffmpeg_installed', return_value=True):
            
            # Create a test MP3 file
            with open(os.path.join(test_dir, "test_song.mp3"), "w") as f:
                f.write("dummy mp3 content")
                
            # Import here to avoid circular import in the test
            
            # Call the function
            normalize_volume_levels(test_dir)
            
            # Assertions
            mock_audio_segment.export.assert_called_once()
        
    def test_set_tags_success(self):
        # Create test directory and file
        test_dir = "./Test_Directory"
        os.makedirs(test_dir, exist_ok=True)
        
        # Create a mock cover photo file
        with open(os.path.join(test_dir, "cover_photo.jpg"), "w") as f:
            f.write("dummy image content")
        
        # Create mock song info
        song_info = {
            "name": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "year": "2021"
        }
        
        # Mock eyed3 load and tag functions
        mock_audio_file = Mock()
        mock_tag = Mock()
        mock_audio_file.tag = mock_tag  # Ensure tag is a mock object
        mock_tag.artist = Mock()
        mock_tag.title = Mock()
        mock_tag.album = Mock()
        mock_tag.year = Mock()
        mock_tag.images.set = Mock()
        mock_tag.lyrics.set = Mock()
        mock_tag.save = Mock()

        # Create mocks for dependencies
        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="Test Lyrics EmbedShare 123")
        
        with patch('eyed3.load', return_value=mock_audio_file), \
                patch('os.remove'), \
                patch('os.path.exists', return_value=True), \
                patch('mimetypes.guess_type', return_value=("image/jpeg", None)), \
                patch('spotube.downloader_utils.get_lyrics', return_value="Test Lyrics"):
            
            # Import function to test
            set_tags(song_info, genius_obj, test_dir)
            
            # Assertions
            assert mock_tag.artist =="Test Artist"
            assert mock_tag.title =="Test Song"
            assert mock_tag.year =="2021"
            assert mock_tag.album =="Test Album"
            mock_tag.lyrics.set.assert_called_once_with("Test Lyrics")
            mock_tag.save.assert_called_once()

if __name__ == "__main__":
    unittest.main()
