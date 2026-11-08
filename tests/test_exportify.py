import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pytest
import requests

from spotube import exportify, spotify_embed
from spotube.exportify import (
    ExportifyLoginRequiredError,
    ExportifyUnavailableError,
    PlaylistNotInLibraryError,
    export_playlist_csv,
    get_exportify_songs,
    parse_exportify_csv,
)

PLAYLIST_ID = "05MWSPxUUWA0d238WFvkKA"
HEADER = (
    "Track URI,ISRC,Track Name,Album Name,Artist Name(s),Release Date,Duration (ms),Popularity,Explicit,Added By,Added At,"
    "Genres,Record Label,Danceability,Energy,Key,Loudness,Mode,Speechiness,Acousticness,Instrumentalness,Liveness,Valence,"
    "Tempo,Time Signature\n"
)
CSV_TEXT = "﻿" + HEADER + (
    'spotify:track:0EKqsoTPmv4eazx1HybrOe,QZ1,"TRAP","EDOG, VOL. 2","Eryn Martin",2021-09-24,144544,10,false,u,t,"rap","label"\n'
    'spotify:track:2Foc5Q5nqNiosCNqttzHof,QZ2,"Get Lucky","Random Access Memories","Daft Punk;Pharrell Williams;Nile Rodgers",2013-05-17,369626,80,false,u,t,"","x"\n'
    'spotify:local:abc,undefined,"Local Song","undefined","undefined",undefined,undefined,0,false,u,t,"",""\n'
    ',,"",,,,,,,,,,\n'
)


class FakePlaywrightError(Exception):
    pass


class FakeTimeoutError(FakePlaywrightError):
    pass


def write_temp_csv(text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    handle.write(text)
    handle.close()
    return handle.name


def make_page(logged_in=True, login_succeeds=True, rows=1, csv_path=None):
    page = MagicMock()
    clicked = {"login": False}

    def wait_for_logout(state=None, timeout=None):
        if logged_in or (clicked["login"] and login_succeeds):
            return
        raise FakeTimeoutError("timeout")

    logout_button = MagicMock()
    logout_button.wait_for.side_effect = wait_for_logout
    export_button = MagicMock()
    export_button.count.return_value = rows
    error_box = MagicMock()
    error_box.inner_text.return_value = "Couldn't export playlist"

    def locator(selector):
        if selector == "#logoutButton":
            return logout_button
        if selector == "#error":
            return error_box
        return export_button

    page.locator.side_effect = locator
    page.click.side_effect = lambda selector: clicked.update(login=selector == "#loginButton")
    download_info = MagicMock()
    download_info.value.path.return_value = csv_path
    page.expect_download.return_value.__enter__.return_value = download_info
    page.expect_download.return_value.__exit__.return_value = False
    page.export_button = export_button
    return page


def fake_api(page, launch_failures=0):
    context = MagicMock(pages=[page])
    playwright = MagicMock()
    playwright.chromium.launch_persistent_context.side_effect = [FakePlaywrightError("not installed")] * launch_failures + [context]
    factory = MagicMock()
    factory.return_value.__enter__.return_value = playwright
    factory.return_value.__exit__.return_value = False
    return (factory, FakePlaywrightError, FakeTimeoutError), playwright, context


class TestExportFlow(unittest.TestCase):
    def setUp(self):
        self.csv_path = write_temp_csv(CSV_TEXT)

    def tearDown(self):
        os.remove(self.csv_path)

    def run_export(self, page, launch_failures=0):
        api, playwright, context = fake_api(page, launch_failures)
        with patch("spotube.exportify._playwright_api", return_value=api):
            result = export_playlist_csv(PLAYLIST_ID, profile_dir="profile")
        return result, playwright, context

    def test_existing_session_exports_headless_with_edge(self):
        page = make_page(csv_path=self.csv_path)

        result, playwright, context = self.run_export(page)

        assert result.lstrip("﻿").startswith("Track URI,ISRC")
        kwargs = playwright.chromium.launch_persistent_context.call_args
        assert kwargs[0][0] == "profile"
        assert kwargs[1]["channel"] == "msedge"
        assert kwargs[1]["headless"] is True
        page.goto.assert_called_once_with(exportify.EXPORTIFY_URL)
        page.click.assert_not_called()
        selectors = [c[0][0] for c in page.locator.call_args_list]
        assert any(f'a[href*="/playlist/{PLAYLIST_ID}"]' in s for s in selectors)
        page.export_button.first.click.assert_called_once()
        context.close.assert_called_once()

    def test_expired_session_logs_in_again_automatically(self):
        page = make_page(logged_in=False, login_succeeds=True, csv_path=self.csv_path)

        result, _, _ = self.run_export(page)

        page.click.assert_called_once_with("#loginButton")
        assert "TRAP" in result

    def test_login_needed_raises_clear_error(self):
        page = make_page(logged_in=False, login_succeeds=False)

        with pytest.raises(ExportifyLoginRequiredError, match="login_exportify"):
            self.run_export(page)

    def test_playlist_not_in_library(self):
        page = make_page(rows=0)

        with pytest.raises(PlaylistNotInLibraryError, match="Follow it in Spotify"):
            self.run_export(page)

    def test_export_timeout_reports_exportify_error(self):
        page = make_page(csv_path=self.csv_path)
        page.expect_download.side_effect = FakeTimeoutError("no download")

        with pytest.raises(ExportifyUnavailableError, match="Couldn't export playlist"):
            self.run_export(page)

    def test_playwright_errors_are_wrapped_and_browser_closed(self):
        page = make_page()
        page.goto.side_effect = FakePlaywrightError("net::ERR_NAME_NOT_RESOLVED")

        api, _, context = fake_api(page)
        with patch("spotube.exportify._playwright_api", return_value=api):
            with pytest.raises(ExportifyUnavailableError, match="ERR_NAME_NOT_RESOLVED"):
                export_playlist_csv(PLAYLIST_ID)
        context.close.assert_called_once()

    def test_falls_back_to_chrome_then_bundled_browser(self):
        page = make_page(csv_path=self.csv_path)

        _, playwright, _ = self.run_export(page, launch_failures=1)
        assert playwright.chromium.launch_persistent_context.call_args[1]["channel"] == "chrome"

        _, playwright, _ = self.run_export(page, launch_failures=2)
        assert playwright.chromium.launch_persistent_context.call_args[1]["channel"] is None

    def test_no_browser_at_all(self):
        page = make_page()

        with pytest.raises(ExportifyUnavailableError, match="playwright install chromium"):
            self.run_export(page, launch_failures=3)

    def test_interactive_login_uses_visible_browser(self):
        page = make_page(logged_in=False, login_succeeds=True)
        api, playwright, _ = fake_api(page)

        with patch("spotube.exportify._playwright_api", return_value=api):
            exportify.login(profile_dir="profile")

        assert playwright.chromium.launch_persistent_context.call_args[1]["headless"] is False
        page.click.assert_called_once_with("#loginButton")


class TestAvailability(unittest.TestCase):
    def test_missing_playwright_gives_install_hint(self):
        with patch.dict(sys.modules, {"playwright": None, "playwright.sync_api": None}):
            with pytest.raises(ExportifyUnavailableError, match=r"spotube\[exportify\]"):
                exportify._playwright_api()

    def test_default_profile_dir_is_per_user(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": os.path.join("C:", "Users", "x", "AppData", "Local")}):
            assert exportify.default_profile_dir().endswith(os.path.join("spotube", "exportify-profile"))


class TestParseCsv(unittest.TestCase):
    def test_parses_exportify_rows(self):
        songs = parse_exportify_csv(CSV_TEXT)

        assert len(songs) == 3
        trap = songs[0]["track"]
        assert trap == {
            "name": "TRAP",
            "uri": "spotify:track:0EKqsoTPmv4eazx1HybrOe",
            "artists": [{"name": "Eryn Martin"}],
            "duration_ms": 144544,
            "album": {"name": "EDOG, VOL. 2", "release_date": "2021-09-24", "images": []},
        }
        assert [a["name"] for a in songs[1]["track"]["artists"]] == ["Daft Punk", "Pharrell Williams", "Nile Rodgers"]

    def test_missing_values_become_empty(self):
        local = parse_exportify_csv(CSV_TEXT)[2]["track"]

        assert local["name"] == "Local Song"
        assert local["artists"] == []
        assert local["duration_ms"] == 0
        assert local["album"]["name"] == ""
        assert local["album"]["release_date"] == ""


class TestGetExportifySongs(unittest.TestCase):
    @patch("spotube.exportify.spotify_embed.fetch_cover_url", side_effect=lambda uri: f"https://img/{uri[-4:]}")
    @patch("spotube.exportify.export_playlist_csv", return_value=CSV_TEXT)
    def test_adds_covers_and_applies_limit(self, mock_export, mock_cover):
        songs = get_exportify_songs(f"https://open.spotify.com/playlist/{PLAYLIST_ID}?si=x", song_number_limit=2)

        mock_export.assert_called_once_with(PLAYLIST_ID, None)
        assert len(songs) == 2
        assert mock_cover.call_count == 2
        assert songs[0]["track"]["album"]["images"] == [{"url": "https://img/brOe"}]
        assert songs[1]["track"]["album"]["images"] == [{"url": "https://img/zHof"}]

    @patch("spotube.exportify.spotify_embed.fetch_cover_url", return_value="")
    @patch("spotube.exportify.export_playlist_csv", return_value=CSV_TEXT)
    def test_songs_feed_existing_pipeline(self, mock_export, mock_cover):
        from spotube.downloader_utils import format_song_data

        info = format_song_data(get_exportify_songs(f"spotify:playlist:{PLAYLIST_ID}")[1])
        assert info == {
            "name": "Get Lucky",
            "artist": "Daft Punk, Pharrell Williams, Nile Rodgers",
            "album": "Random Access Memories",
            "year": "2013",
            "duration": 369626,
            "url": "",
        }

    @patch("spotube.exportify.export_playlist_csv", return_value=HEADER)
    def test_empty_export_raises(self, mock_export):
        with pytest.raises(ExportifyUnavailableError, match="no tracks"):
            get_exportify_songs(f"spotify:playlist:{PLAYLIST_ID}")


class TestCoverLookup(unittest.TestCase):
    @patch("spotube.spotify_embed.fetch_embed_entity")
    def test_non_track_uri_skips_request(self, mock_fetch):
        assert spotify_embed.fetch_cover_url("spotify:local:abc") == ""
        mock_fetch.assert_not_called()

    @patch("spotube.spotify_embed.fetch_embed_entity", side_effect=requests.ConnectionError("offline"))
    def test_failure_returns_empty(self, mock_fetch):
        assert spotify_embed.fetch_cover_url("spotify:track:abc") == ""


class TestDownloadManagerLogin(unittest.TestCase):
    @patch("spotube.download_manager.exportify.login")
    def test_login_exportify_delegates(self, mock_login):
        from spotube.download_manager import DownloadManager
        DownloadManager().login_exportify()
        mock_login.assert_called_once_with()
