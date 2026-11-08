import csv
import importlib.util
import io
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

from spotube import spotify_embed

EXPORTIFY_URL = "https://exportify.net/"
BROWSER_CHANNELS = ("msedge", "chrome", None)
SESSION_CHECK_TIMEOUT_MS = 5_000
AUTO_LOGIN_TIMEOUT_MS = 30_000
INTERACTIVE_LOGIN_TIMEOUT_MS = 300_000
PLAYLIST_TABLE_TIMEOUT_MS = 120_000
EXPORT_TIMEOUT_MS = 600_000
PLAYLISTS_LOADED_JS = "() => /\\d+ playlists/.test(document.getElementById('subtitle')?.textContent || '')"
MISSING_VALUES = {"", "undefined", "null"}


class ExportifyUnavailableError(Exception):
    pass


class ExportifyLoginRequiredError(ExportifyUnavailableError):
    pass


class PlaylistNotInLibraryError(ExportifyUnavailableError):
    pass


def is_available():
    return importlib.util.find_spec("playwright") is not None


def default_profile_dir():
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME") or os.path.join(Path.home(), ".local", "share")
    return os.path.join(base, "spotube", "exportify-profile")


def _playwright_api():
    try:
        from playwright.sync_api import Error, TimeoutError, sync_playwright
    except ImportError as e:
        raise ExportifyUnavailableError("Exportify support is not installed, run: pip install spotube[exportify]") from e
    return sync_playwright, Error, TimeoutError


def _launch_context(playwright, profile_dir, headless, playwright_error):
    failures = []
    for channel in BROWSER_CHANNELS:
        try:
            return playwright.chromium.launch_persistent_context(profile_dir, channel=channel, headless=headless, accept_downloads=True)
        except playwright_error as e:
            failures.append(f"{channel or 'bundled chromium'}: {str(e).splitlines()[0]}")
    raise ExportifyUnavailableError(
        "No usable browser found. Install Microsoft Edge or Google Chrome, or run: playwright install chromium. "
        + " | ".join(failures)
    )


@contextmanager
def _browser(profile_dir, headless):
    sync_playwright, playwright_error, timeout_error = _playwright_api()
    with sync_playwright() as playwright:
        context = _launch_context(playwright, profile_dir or default_profile_dir(), headless, playwright_error)
        try:
            yield context, timeout_error
        except ExportifyUnavailableError:
            raise
        except playwright_error as e:
            raise ExportifyUnavailableError(f"Browser automation failed: {e}") from e
        finally:
            context.close()


def _open_logged_in_page(context, login_timeout_ms, timeout_error):
    page = context.pages[0] if context.pages else context.new_page()
    page.goto(EXPORTIFY_URL)
    logout_button = page.locator("#logoutButton")
    try:
        logout_button.wait_for(state="attached", timeout=SESSION_CHECK_TIMEOUT_MS)
        return page
    except timeout_error:
        pass

    page.click("#loginButton")
    try:
        logout_button.wait_for(state="attached", timeout=login_timeout_ms)
    except timeout_error as e:
        raise ExportifyLoginRequiredError(
            "Spotify login required for Exportify. Run `spotube login` (or DownloadManager().login_exportify()) once and sign in."
        ) from e
    return page


def _download_playlist_csv(page, playlist_id, timeout_error):
    try:
        page.wait_for_function(PLAYLISTS_LOADED_JS, timeout=PLAYLIST_TABLE_TIMEOUT_MS)
    except timeout_error as e:
        raise ExportifyUnavailableError("Exportify did not finish loading your playlists") from e

    export_button = page.locator(f'#playlistsContainer tr:has(a[href*="/playlist/{playlist_id}"]) button[id^="export"]')
    if export_button.count() == 0:
        raise PlaylistNotInLibraryError(
            f"Playlist {playlist_id} is not in your Spotify library. Follow it in Spotify, then try again."
        )

    try:
        with page.expect_download(timeout=EXPORT_TIMEOUT_MS) as download_info:
            export_button.first.click()
    except timeout_error as e:
        details = page.locator("#error").inner_text().strip()
        raise ExportifyUnavailableError(f"Exportify did not produce a file. {details}".strip()) from e

    with open(download_info.value.path(), encoding="utf-8-sig") as csv_file:
        return csv_file.read()


def login(profile_dir=None):
    with _browser(profile_dir, headless=False) as (context, timeout_error):
        _open_logged_in_page(context, INTERACTIVE_LOGIN_TIMEOUT_MS, timeout_error)


def export_playlist_csv(playlist_id, profile_dir=None):
    with _browser(profile_dir, headless=True) as (context, timeout_error):
        page = _open_logged_in_page(context, AUTO_LOGIN_TIMEOUT_MS, timeout_error)
        return _download_playlist_csv(page, playlist_id, timeout_error)


def _clean(value):
    value = (value or "").strip()
    return "" if value in MISSING_VALUES else value


def parse_exportify_csv(csv_text):
    songs = []
    for row in csv.DictReader(io.StringIO(csv_text.lstrip("﻿"))):
        name = _clean(row.get("Track Name"))
        if not name:
            continue
        duration = _clean(row.get("Duration (ms)"))
        songs.append({
            "track": {
                "name": name,
                "uri": _clean(row.get("Track URI")),
                "artists": [{"name": artist.strip()} for artist in _clean(row.get("Artist Name(s)")).split(";") if artist.strip()],
                "duration_ms": int(float(duration)) if duration else 0,
                "album": {
                    "name": _clean(row.get("Album Name")),
                    "release_date": _clean(row.get("Release Date")),
                    "images": [],
                },
            }
        })
    return songs


def get_exportify_songs(playlist_url, song_number_limit=0, profile_dir=None):
    songs = parse_exportify_csv(export_playlist_csv(spotify_embed.parse_playlist_id(playlist_url), profile_dir))
    if not songs:
        raise ExportifyUnavailableError("Exportify returned no tracks for this playlist")
    if song_number_limit > 0:
        songs = songs[:song_number_limit]

    with ThreadPoolExecutor(max_workers=spotify_embed.MAX_WORKERS) as pool:
        covers = list(pool.map(spotify_embed.fetch_cover_url, [song["track"]["uri"] for song in songs]))
    for song, cover in zip(songs, covers, strict=True):
        if cover:
            song["track"]["album"]["images"] = [{"url": cover}]
    return songs
