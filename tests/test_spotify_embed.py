import json
import unittest
from unittest.mock import Mock, patch

import pytest
import requests
from spotipy.exceptions import SpotifyException

from spotube import spotify_embed
from spotube.authenticator import Authenticator
from spotube.downloader_utils import fetch_playlist_songs, format_song_data
from spotube.spotify_embed import (
    PlaylistUnavailableError,
    build_song,
    fetch_embed_entity,
    get_embed_songs,
    largest_image_url,
    lookup_album_name,
    parse_playlist_id,
)

PLAYLIST_ID = "05MWSPxUUWA0d238WFvkKA"


def embed_page(entity=None, status=None):
    page_props = {"state": {"data": {"entity": entity}}} if entity is not None else {"status": status}
    payload = json.dumps({"props": {"pageProps": page_props}})
    return Mock(text=f'<html><script id="__NEXT_DATA__" type="application/json">{payload}</script></html>', raise_for_status=Mock())


def playlist_item(track_id, title="Song", subtitle="Artist", duration=200000):
    return {"uri": f"spotify:track:{track_id}", "title": title, "subtitle": subtitle, "duration": duration}


TRACK_DETAILS = {
    "name": "TRAP",
    "artists": [{"name": "Eryn Martin", "uri": "spotify:artist:x"}],
    "duration": 144544,
    "releaseDate": {"isoString": "2021-09-24T00:00:00Z"},
    "visualIdentity": {"image": [
        {"url": "https://img/300", "maxWidth": 300},
        {"url": "https://img/640", "maxWidth": 640},
        {"url": "https://img/64", "maxWidth": 64},
    ]},
}


class TestParsePlaylistId(unittest.TestCase):
    def test_accepts_common_link_formats(self):
        for link in (
            f"https://open.spotify.com/playlist/{PLAYLIST_ID}?si=da202feed7f54d18",
            f"https://open.spotify.com/intl-de/playlist/{PLAYLIST_ID}",
            f"spotify:playlist:{PLAYLIST_ID}",
        ):
            assert parse_playlist_id(link) == PLAYLIST_ID

    def test_rejects_non_playlist_links(self):
        for link in ("https://open.spotify.com/track/0EKqsoTPmv4eazx1HybrOe", "not a link", None):
            with pytest.raises(PlaylistUnavailableError):
                parse_playlist_id(link)


class TestFetchEmbedEntity(unittest.TestCase):
    @patch("spotube.spotify_embed.requests.get")
    def test_returns_entity(self, mock_get):
        mock_get.return_value = embed_page({"type": "playlist", "trackList": []})

        assert fetch_embed_entity("playlist", PLAYLIST_ID) == {"type": "playlist", "trackList": []}
        assert mock_get.call_args[0][0] == f"https://open.spotify.com/embed/playlist/{PLAYLIST_ID}"
        assert mock_get.call_args[1]["timeout"] == spotify_embed.REQUEST_TIMEOUT

    @patch("spotube.spotify_embed.requests.get")
    def test_missing_playlist_raises(self, mock_get):
        mock_get.return_value = embed_page(status=404)
        with pytest.raises(PlaylistUnavailableError, match="404"):
            fetch_embed_entity("playlist", "0" * 22)

    @patch("spotube.spotify_embed.requests.get")
    def test_unexpected_page_raises(self, mock_get):
        mock_get.return_value = Mock(text="<html>changed layout</html>", raise_for_status=Mock())
        with pytest.raises(PlaylistUnavailableError):
            fetch_embed_entity("playlist", PLAYLIST_ID)


class TestLookupAlbumName(unittest.TestCase):
    @patch("spotube.spotify_embed.requests.get")
    def test_matches_artist_and_duration(self, mock_get):
        mock_get.return_value.json.return_value = {"data": [
            {"artist": {"name": "Someone Else"}, "duration": 144, "album": {"title": "Wrong"}},
            {"artist": {"name": "eryn martin"}, "duration": 145, "album": {"title": "EDOG, VOL. 2"}},
        ]}
        assert lookup_album_name("TRAP", "Eryn Martin", 144544) == "EDOG, VOL. 2"

    @patch("spotube.spotify_embed.requests.get")
    def test_rejects_different_duration(self, mock_get):
        mock_get.return_value.json.return_value = {"data": [
            {"artist": {"name": "Eryn Martin"}, "duration": 300, "album": {"title": "Extended"}},
        ]}
        assert lookup_album_name("TRAP", "Eryn Martin", 144544) == ""

    @patch("spotube.spotify_embed.requests.get", side_effect=requests.ConnectionError("offline"))
    def test_network_error_returns_empty(self, mock_get):
        assert lookup_album_name("TRAP", "Eryn Martin", 144544) == ""


class TestBuildSong(unittest.TestCase):
    def test_largest_image_url(self):
        assert largest_image_url(TRACK_DETAILS["visualIdentity"]["image"]) == "https://img/640"
        assert largest_image_url(None) == ""

    @patch("spotube.spotify_embed.lookup_album_name", return_value="EDOG, VOL. 2")
    @patch("spotube.spotify_embed.fetch_embed_entity", return_value=TRACK_DETAILS)
    def test_song_is_compatible_with_format_song_data(self, mock_fetch, mock_album):
        song = build_song(playlist_item("0EKqsoTPmv4eazx1HybrOe", "TRAP", "Eryn Martin", 144544))

        assert format_song_data(song) == {
            "name": "TRAP",
            "artist": "Eryn Martin",
            "album": "EDOG, VOL. 2",
            "year": "2021",
            "duration": 144544,
            "url": "https://img/640",
        }
        mock_fetch.assert_called_once_with("track", "0EKqsoTPmv4eazx1HybrOe")
        mock_album.assert_called_once_with("TRAP", "Eryn Martin", 144544)

    @patch("spotube.spotify_embed.lookup_album_name", return_value="")
    @patch("spotube.spotify_embed.fetch_embed_entity", side_effect=requests.ConnectionError("offline"))
    def test_falls_back_to_playlist_data(self, mock_fetch, mock_album):
        song = build_song(playlist_item("abc", "Duet", "Artist A, Artist B", 180000))

        info = format_song_data(song)
        assert info["name"] == "Duet"
        assert info["artist"] == "Artist A, Artist B"
        assert info["duration"] == 180000
        assert info["url"] == ""


class TestGetEmbedSongs(unittest.TestCase):
    @patch("spotube.spotify_embed.build_song", side_effect=lambda item: item["uri"])
    @patch("spotube.spotify_embed.fetch_embed_entity")
    def test_skips_non_tracks_and_applies_limit(self, mock_fetch, mock_build):
        mock_fetch.return_value = {"trackList": [
            playlist_item("a"),
            {"uri": "spotify:episode:podcast", "title": "Episode"},
            playlist_item("b"),
            playlist_item("c"),
        ]}

        assert get_embed_songs(f"spotify:playlist:{PLAYLIST_ID}", song_number_limit=2) == ["spotify:track:a", "spotify:track:b"]
        mock_fetch.assert_called_once_with("playlist", PLAYLIST_ID)

    @patch("builtins.print")
    @patch("spotube.spotify_embed.build_song", side_effect=lambda item: item["uri"])
    @patch("spotube.spotify_embed.fetch_embed_entity")
    def test_warns_when_playlist_may_be_truncated(self, mock_fetch, mock_build, mock_print):
        mock_fetch.return_value = {"trackList": [playlist_item(str(i)) for i in range(spotify_embed.EMBED_TRACK_LIMIT)]}

        songs = get_embed_songs(f"spotify:playlist:{PLAYLIST_ID}")
        assert len(songs) == spotify_embed.EMBED_TRACK_LIMIT
        assert "truncated" in mock_print.call_args[0][0]

    @patch("builtins.print")
    @patch("spotube.spotify_embed.build_song", side_effect=lambda item: item["uri"])
    @patch("spotube.spotify_embed.fetch_embed_entity")
    def test_no_warning_for_short_playlist(self, mock_fetch, mock_build, mock_print):
        mock_fetch.return_value = {"trackList": [playlist_item("a")]}

        get_embed_songs(f"spotify:playlist:{PLAYLIST_ID}")
        mock_print.assert_not_called()


SHORT_LIST = [playlist_item("a")]
FULL_LIST = [playlist_item(str(i)) for i in range(spotify_embed.EMBED_TRACK_LIMIT)]


@patch("spotube.downloader_utils.exportify.is_available", return_value=True)
@patch("spotube.downloader_utils.exportify.get_exportify_songs", return_value=["x1"])
@patch("spotube.downloader_utils.spotify_embed.build_songs", return_value=["e1"])
class TestPlaylistSourceSelection(unittest.TestCase):
    @patch("spotube.downloader_utils.spotify_embed.get_embed_track_list")
    @patch("spotube.downloader_utils.get_songs", return_value=["s1", "s2", "s3"])
    def test_uses_official_api_when_available(self, mock_api, mock_list, mock_build, mock_export, mock_available):
        assert fetch_playlist_songs("link", Mock(spotify_auth=Mock()), 2) == ["s1", "s2"]
        mock_list.assert_not_called()
        mock_export.assert_not_called()

    @patch("spotube.downloader_utils.spotify_embed.get_embed_track_list", return_value=SHORT_LIST)
    @patch("spotube.downloader_utils.get_songs", side_effect=SpotifyException(403, -1, "Active premium subscription required"))
    def test_falls_back_to_embed_when_api_refuses(self, mock_api, mock_list, mock_build, mock_export, mock_available):
        assert fetch_playlist_songs("link", Mock(spotify_auth=Mock()), 0) == ["e1"]
        mock_build.assert_called_once_with(SHORT_LIST, 0)
        mock_export.assert_not_called()

    @patch("spotube.downloader_utils.spotify_embed.get_embed_track_list", return_value=SHORT_LIST)
    @patch("spotube.downloader_utils.get_songs")
    def test_uses_embed_without_credentials(self, mock_api, mock_list, mock_build, mock_export, mock_available):
        assert fetch_playlist_songs("link", Mock(spotify_auth=None), 5) == ["e1"]
        mock_api.assert_not_called()
        mock_build.assert_called_once_with(SHORT_LIST, 5)

    @patch("spotube.downloader_utils.spotify_embed.get_embed_track_list", return_value=FULL_LIST)
    def test_uses_exportify_for_possibly_truncated_playlist(self, mock_list, mock_build, mock_export, mock_available):
        assert fetch_playlist_songs("link", Mock(spotify_auth=None), 0) == ["x1"]
        mock_export.assert_called_once_with("link", 0)
        mock_build.assert_not_called()

    @patch("spotube.downloader_utils.spotify_embed.get_embed_track_list", return_value=FULL_LIST)
    def test_skips_exportify_when_limit_fits_in_public_view(self, mock_list, mock_build, mock_export, mock_available):
        assert fetch_playlist_songs("link", Mock(spotify_auth=None), 50) == ["e1"]
        mock_export.assert_not_called()

    @patch("spotube.downloader_utils.spotify_embed.get_embed_track_list", return_value=FULL_LIST)
    def test_skips_exportify_when_disabled(self, mock_list, mock_build, mock_export, mock_available):
        assert fetch_playlist_songs("link", Mock(spotify_auth=None), 0, use_exportify=False) == ["e1"]
        mock_export.assert_not_called()

    @patch("spotube.downloader_utils.spotify_embed.get_embed_track_list", return_value=FULL_LIST)
    def test_skips_exportify_when_not_installed(self, mock_list, mock_build, mock_export, mock_available):
        mock_available.return_value = False
        assert fetch_playlist_songs("link", Mock(spotify_auth=None), 0) == ["e1"]
        mock_export.assert_not_called()

    @patch("builtins.print")
    @patch("spotube.downloader_utils.spotify_embed.get_embed_track_list", return_value=FULL_LIST)
    def test_falls_back_to_first_100_when_exportify_fails(self, mock_list, mock_print, mock_build, mock_export, mock_available):
        from spotube.exportify import PlaylistNotInLibraryError
        mock_export.side_effect = PlaylistNotInLibraryError("Follow it in Spotify")

        assert fetch_playlist_songs("link", Mock(spotify_auth=None), 0) == ["e1"]
        mock_build.assert_called_once_with(FULL_LIST, 0)
        assert "Follow it in Spotify" in mock_print.call_args[0][0]


class TestOptionalCredentials(unittest.TestCase):
    def test_authenticator_without_keys(self):
        auth = Authenticator()
        assert auth.spotify_auth is None
        assert auth.genius_auth is None

    @patch("spotube.authenticator.lyricsgenius.Genius")
    def test_authenticator_with_genius_only(self, mock_genius):
        auth = Authenticator(genius_api_key="token")
        assert auth.spotify_auth is None
        assert auth.genius_auth is mock_genius.return_value

    def test_download_manager_without_keys(self):
        from spotube.download_manager import DownloadManager
        manager = DownloadManager(directory="./Test_Directory")
        assert manager.authenticator.spotify_auth is None
        assert manager.authenticator.genius_auth is None

    @patch("spotube.download_manager.spotify_embed.fetch_embed_entity")
    def test_validate_url_without_keys(self, mock_fetch):
        from spotube.download_manager import DownloadManager
        manager = DownloadManager()

        assert manager.validate_playlist_url(f"https://open.spotify.com/playlist/{PLAYLIST_ID}") is True
        mock_fetch.side_effect = PlaylistUnavailableError("gone")
        assert manager.validate_playlist_url(f"https://open.spotify.com/playlist/{PLAYLIST_ID}") is False
        assert manager.validate_playlist_url("https://example.com") is False
