import os
import re

import pytest
import requests

from spotube import downloader_utils, exportify, spotify_embed

pytestmark = pytest.mark.live

SMALL_PLAYLIST = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
LARGE_PLAYLIST = "https://open.spotify.com/playlist/37i9dQZF1DX4UtSsGT1Sbe"
SHORT_VIDEO = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
YOUTUBE_BLOCK_MARKERS = ("Sign in to confirm", "confirm you're not a bot", "HTTP Error 429")
EXPORTIFY_JS_URL = "https://exportify.net/exportify.js"
EXPORTIFY_CSV_COLUMNS = ("Track URI", "Track Name", "Album Name", "Artist Name(s)", "Release Date", "Duration (ms)")


def skip_if_youtube_blocks(error):
    text = f"{error} {error.__cause__ or ''}"
    if any(marker in text for marker in YOUTUBE_BLOCK_MARKERS):
        pytest.skip(f"YouTube is blocking this machine's IP, not a code problem: {text[:200]}")


class TestSpotifyEmbed:
    def test_small_playlist_has_expected_shape(self):
        track_list = spotify_embed.get_embed_track_list(SMALL_PLAYLIST)

        assert 0 < len(track_list) < spotify_embed.EMBED_TRACK_LIMIT
        assert not spotify_embed.needs_full_list(track_list, 0)
        first = track_list[0]
        assert first["uri"].startswith("spotify:track:")
        assert first["title"] and first["subtitle"]
        assert first["duration"] > 0

    def test_track_details_fill_album_metadata(self):
        song = spotify_embed.build_song(spotify_embed.get_embed_track_list(SMALL_PLAYLIST)[0])["track"]

        assert song["name"]
        assert song["artists"] and song["artists"][0]["name"]
        assert song["duration_ms"] > 0
        assert re.match(r"\d{4}-\d{2}-\d{2}", song["album"]["release_date"])
        assert song["album"]["images"][0]["url"].startswith("https://")

    def test_large_playlist_is_still_capped_at_100(self):
        track_list = spotify_embed.get_embed_track_list(LARGE_PLAYLIST)

        assert len(track_list) == spotify_embed.EMBED_TRACK_LIMIT
        assert spotify_embed.needs_full_list(track_list, 0)

    def test_invalid_playlist_is_rejected(self):
        with pytest.raises(spotify_embed.PlaylistUnavailableError):
            spotify_embed.fetch_embed_entity("playlist", "0000000000000000000000")


class TestDeezer:
    def test_album_lookup(self):
        assert spotify_embed.lookup_album_name("Get Lucky", "Daft Punk", 369626) == "Random Access Memories"


class TestYouTube:
    def test_search_returns_urls_and_durations(self):
        results = downloader_utils.search_videos("Daft Punk Get Lucky")

        assert results
        assert any(result.get("duration") for result in results)
        assert all(result.get("url") or result.get("id") for result in results)

    @pytest.mark.ffmpeg
    def test_download_produces_mp3(self, tmp_path):
        downloader = downloader_utils.create_audio_downloader(str(tmp_path))
        song = {"name": "Me at the zoo"}

        try:
            downloader_utils.download_song(SHORT_VIDEO, song, downloader, str(tmp_path), attempts=1)
        except RuntimeError as e:
            skip_if_youtube_blocks(e)
            raise

        mp3 = tmp_path / "Me at the zoo.mp3"
        assert mp3.stat().st_size > 50_000
        assert downloader_utils.measure_mean_volume(str(mp3)) < 0


class TestGenius:
    def test_lyrics_lookup(self):
        token = os.environ.get("GENIUS_ACCESS_TOKEN")
        if not token:
            pytest.skip("GENIUS_ACCESS_TOKEN is not set")
        from spotube.authenticator import Authenticator

        try:
            lyrics = downloader_utils.get_lyrics("Get Lucky", "Daft Punk, Pharrell Williams", Authenticator(genius_api_key=token).genius_auth)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                pytest.skip("Genius is blocking this machine's IP")
            raise

        assert lyrics and "lucky" in lyrics.lower()


@pytest.fixture(scope="module")
def site():
    index = requests.get(exportify.EXPORTIFY_URL, timeout=20)
    script = requests.get(EXPORTIFY_JS_URL, timeout=20)
    index.raise_for_status()
    script.raise_for_status()
    return index.text, script.text


class TestExportifyContract:
    def test_page_elements_used_for_login(self, site):
        index, script = site

        assert 'id="loginButton"' in index
        assert 'id="subtitle"' in index
        assert 'id="playlistsContainer"' in index
        assert 'id="logoutButton"' in script

    def test_playlist_table_markers(self, site):
        _, script = site

        assert re.search(r"playlists\.length\s*\+\s*' playlists", script), "subtitle no longer reads 'N playlists'"
        assert re.search(r'id:\s*"export"\s*\+\s*i', script), "export buttons are no longer numbered export0, export1, ..."
        assert re.search(r"href:\s*playlist\.external_urls\.spotify", script), "playlist rows no longer link to the Spotify URL"

    def test_csv_format(self, site):
        _, script = site
        header = re.search(r'"(Track URI,[^"]+)"', script)

        assert header, "CSV header not found"
        columns = header.group(1).split(",")
        for column in EXPORTIFY_CSV_COLUMNS:
            assert column in columns
        assert ".join(';')" in script, "artists are no longer separated by ';'"


class TestExportifyEndToEnd:
    def test_full_playlist_export(self):
        playlist = os.environ.get("SPOTUBE_LIVE_EXPORTIFY_PLAYLIST")
        if not playlist or not exportify.is_available():
            pytest.skip("set SPOTUBE_LIVE_EXPORTIFY_PLAYLIST to a 100+ track playlist in your library after login_exportify()")

        songs = exportify.get_exportify_songs(playlist)

        assert len(songs) > spotify_embed.EMBED_TRACK_LIMIT
        assert all(song["track"]["name"] for song in songs)
