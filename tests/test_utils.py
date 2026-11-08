import os
import unittest
from unittest.mock import Mock, patch

import pytest

from spotube.authenticator import Authenticator
from spotube.downloader_utils import (
    download_image,
    format_artists,
    format_song_data,
    get_link,
    get_lyrics,
    search_videos,
    set_tags,
)


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


class TestUtils(unittest.TestCase):
    def test_get_lyrics_with_feature(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="These are the lyrics\n")
        
        result = get_lyrics("Song ft. Artist", "Artist", genius_obj)
        
        assert result == "These are the lyrics"

    def test_get_lyrics_without_feature(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="These are the lyrics\n")
        
        result = get_lyrics("Song", "Artist", genius_obj)
        
        assert result == "These are the lyrics"

    def test_get_lyrics_no_lyrics_found(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = None
        
        result = get_lyrics("Song", "Artist", genius_obj)
        
        assert result is None

    def test_get_lyrics_with_multiple_features(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="These are the lyrics\n")
        
        result = get_lyrics("Song (feat. Artist1, Artist2)", "Artist", genius_obj)
        
        assert result == "These are the lyrics"

    def test_get_lyrics_with_different_feature_formats(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="These are the lyrics\n")
        
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

    def test_get_lyrics_keeps_last_words_intact(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="[Chorus]\nWe're up all night to get lucky")

        assert get_lyrics("Get Lucky", "Daft Punk", genius_obj) == "[Chorus]\nWe're up all night to get lucky"

    def test_get_lyrics_searches_primary_artist_first(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="Lyrics")

        assert get_lyrics("Get Lucky", "Daft Punk, Pharrell Williams", genius_obj) == "Lyrics"
        genius_obj.search_song.assert_called_once_with("Get Lucky", "Daft Punk")

    def test_get_lyrics_falls_back_to_full_artist_string(self):
        genius_obj = Mock()
        genius_obj.search_song.side_effect = [None, Mock(lyrics="Lyrics")]

        assert get_lyrics("See You Again", "Tyler, The Creator", genius_obj) == "Lyrics"
        assert [c.args for c in genius_obj.search_song.call_args_list] == [
            ("See You Again", "Tyler"),
            ("See You Again", "Tyler, The Creator"),
        ]

    def test_get_lyrics_empty_lyrics_returns_none(self):
        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="")

        assert get_lyrics("Song", "Artist", genius_obj) is None

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

    def test_set_tags_success(self):
        test_dir = "./Test_Directory"
        os.makedirs(test_dir, exist_ok=True)
        
        with open(os.path.join(test_dir, "cover_photo.jpg"), "w") as f:
            f.write("dummy image content")
        
        song_info = {
            "name": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "year": "2021"
        }
        
        mock_audio_file = Mock()
        mock_tag = Mock()
        mock_audio_file.tag = mock_tag
        mock_tag.artist = Mock()
        mock_tag.title = Mock()
        mock_tag.album = Mock()
        mock_tag.recording_date = Mock()
        mock_tag.images.set = Mock()
        mock_tag.lyrics.set = Mock()
        mock_tag.save = Mock()

        genius_obj = Mock()
        genius_obj.search_song.return_value = Mock(lyrics="Test Lyrics EmbedShare 123")
        
        with patch('eyed3.load', return_value=mock_audio_file), \
                patch('os.remove'), \
                patch('os.path.exists', return_value=True), \
                patch('mimetypes.guess_type', return_value=("image/jpeg", None)), \
                patch('spotube.downloader_utils.get_lyrics', return_value="Test Lyrics"):
            
            set_tags(song_info, genius_obj, test_dir)
            
            assert mock_tag.artist =="Test Artist"
            assert mock_tag.title =="Test Song"
            assert mock_tag.recording_date == "2021"
            assert mock_tag.album =="Test Album"
            mock_tag.lyrics.set.assert_called_once_with("Test Lyrics")
            mock_tag.save.assert_called_once()
            

class TestOptionalMetadata(unittest.TestCase):
    def test_set_tags_without_genius_or_cover(self):
        mock_audio_file = Mock()
        song_info = {"name": "Song", "artist": "A, B", "album": "", "year": ""}

        with patch('eyed3.load', return_value=mock_audio_file), \
                patch('os.path.exists', return_value=False), \
                patch('os.remove') as mock_remove, \
                patch('spotube.downloader_utils.get_lyrics') as mock_lyrics:
            set_tags(song_info, None, "./Test_Directory")

        mock_lyrics.assert_not_called()
        mock_remove.assert_not_called()
        mock_audio_file.tag.images.set.assert_not_called()
        mock_audio_file.tag.save.assert_called_once()
        assert mock_audio_file.tag.artist == "A; B"

    @patch('spotube.downloader_utils.requests.get')
    def test_download_image_skips_missing_url(self, mock_get):
        download_image({"url": ""}, "./Test_Directory")
        mock_get.assert_not_called()


class TestVideoSearch(unittest.TestCase):
    SONG = {"name": "Song", "artist": "Artist", "duration": 200000}

    @patch('spotube.downloader_utils.search_videos')
    def test_get_link_picks_closest_duration(self, mock_search):
        mock_search.return_value = [
            {"id": "far", "url": "https://www.youtube.com/watch?v=far", "duration": 260},
            {"id": "close", "url": "https://www.youtube.com/watch?v=close", "duration": 201},
            {"id": "mid", "url": "https://www.youtube.com/watch?v=mid", "duration": 215},
        ]
        assert get_link(self.SONG) == "https://www.youtube.com/watch?v=close"
        mock_search.assert_called_once_with("Song Artist")

    @patch('spotube.downloader_utils.search_videos')
    def test_get_link_skips_results_without_duration(self, mock_search):
        mock_search.return_value = [
            {"id": "live", "url": "https://www.youtube.com/watch?v=live", "duration": None},
            {"id": "ok", "duration": 199.5},
        ]
        assert get_link(self.SONG) == "https://www.youtube.com/watch?v=ok"

    @patch('spotube.downloader_utils.search_videos')
    def test_get_link_rejects_results_too_far_off(self, mock_search):
        mock_search.return_value = [{"id": "x", "url": "https://www.youtube.com/watch?v=x", "duration": 500}]
        assert get_link(self.SONG) == ""

    @patch('spotube.downloader_utils.search_videos', side_effect=Exception("network down"))
    def test_get_link_returns_empty_on_search_error(self, mock_search):
        assert get_link(self.SONG) == ""

    @patch('spotube.downloader_utils.YoutubeDL')
    def test_search_videos_uses_flat_ytsearch(self, mock_ydl):
        client = mock_ydl.return_value.__enter__.return_value
        client.extract_info.return_value = {"entries": [{"id": "a"}]}

        assert search_videos("Song Artist") == [{"id": "a"}]
        client.extract_info.assert_called_once_with("ytsearch3:Song Artist", download=False)
        assert mock_ydl.call_args[0][0]["extract_flat"] is True

    @patch('spotube.downloader_utils.YoutubeDL')
    def test_search_videos_handles_empty_result(self, mock_ydl):
        mock_ydl.return_value.__enter__.return_value.extract_info.return_value = None
        assert search_videos("nothing") == []


class TestAuthenticator(unittest.TestCase):
    @patch('spotube.authenticator.spotipy.Spotify')
    @patch('spotube.authenticator.SpotifyClientCredentials')
    @patch('spotube.authenticator.lyricsgenius.Genius')
    def test_genius_created_with_token_only(self, mock_genius, mock_credentials, mock_spotify):
        auth = Authenticator("id", "secret", "token")

        mock_genius.assert_called_once_with("token")
        mock_credentials.assert_called_once_with(client_id="id", client_secret="secret")
        assert auth.genius_auth is mock_genius.return_value
        assert auth.spotify_auth is mock_spotify.return_value


if __name__ == "__main__":
    unittest.main()
