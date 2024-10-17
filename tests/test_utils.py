import unittest
import pytest
import os
import shutil
from spotube.dependency_handler import DependencyHandler
from unittest.mock import Mock
from spotube.downloader_utils import get_lyrics

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

if __name__ == "__main__":
    unittest.main()
