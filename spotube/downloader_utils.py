import contextlib
import logging
import math
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import eyed3
import requests
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOauthError
from tqdm import tqdm
from yt_dlp import YoutubeDL

from spotube import exportify, spotify_embed

logger = logging.getLogger(__name__)

COVER_PHOTO = "/cover_photo.jpg"
DOWNLOADED_SONG = "downloaded_song.mp3"
DOWNLOAD_ATTEMPTS = 4
ERROR_LOG = "errors.log"
TARGET_LOUDNESS_DBFS = -14.0
NORMALIZED_BITRATE = "192k"
NORMALIZED_MARKER = "compressed"
MEAN_VOLUME_PATTERN = re.compile(r"mean_volume:\s*(-?[\d.]+|-inf) dB")
FFMPEG_MISSING_MESSAGE = (
    "ffmpeg and ffprobe were not found on PATH. Install ffmpeg (Windows: winget install ffmpeg, "
    "macOS: brew install ffmpeg, Debian/Ubuntu: sudo apt install ffmpeg) and try again."
)
SEPARATOR_CHARS = re.compile(r"[/\\|]")
INVALID_FILENAME_CHARS = re.compile(r'[<>:"?*\x00-\x1f]')
WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
MAX_FILENAME_LENGTH = 150
PARTIAL_FILE_PATTERNS = ("downloaded_song.*", "cover_photo.jpg", "*.normalizing.mp3")


class DownloadResult(NamedTuple):
    total: int
    success: int
    failure: int


class FFmpegNotFoundError(RuntimeError):
    pass


def ffmpeg_installed():
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def configure_error_log(path=ERROR_LOG):
    package_logger = logging.getLogger("spotube")
    if package_logger.handlers:
        return
    handler = logging.FileHandler(path, delay=True, encoding="utf-8")
    handler.setLevel(logging.WARNING)
    handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(message)s"))
    package_logger.addHandler(handler)


def safe_filename(name):
    cleaned = " ".join(SEPARATOR_CHARS.sub("-", name).split())
    cleaned = " ".join(INVALID_FILENAME_CHARS.sub("", cleaned).split())[:MAX_FILENAME_LENGTH].strip(" .")
    if not cleaned:
        return "Untitled"
    if cleaned.split(".")[0].upper() in WINDOWS_RESERVED_NAMES:
        cleaned += "_"
    return cleaned


def song_path(directory, song_info):
    primary_artist = (song_info.get("artist") or "").split(",")[0].strip()
    name = f"{primary_artist} - {song_info['name']}" if primary_artist else song_info["name"]
    return os.path.join(directory, safe_filename(name) + ".mp3")


def remove_partial_files(directory):
    if not os.path.isdir(directory):
        return
    for pattern in PARTIAL_FILE_PATTERNS:
        for path in Path(directory).glob(pattern):
            try:
                path.unlink()
            except OSError as e:
                logger.error(f"Could not remove partial file {path}: {e}")


def get_lyrics(name_search, artist_search, genius_obj):
    sep1 = "ft."
    sep2 = "feat"
    sep3 = "(feat"
    sep4 = "(ft."
    sep5 = "(feat."
    name_search = name_search.split(sep1)[0]
    name_search = name_search.split(sep2)[0]
    name_search = name_search.split(sep3)[0]
    name_search = name_search.split(sep4)[0]
    name_search = name_search.split(sep5)[0].strip()

    primary_artist = artist_search.split(",")[0].strip()
    for artist in dict.fromkeys([primary_artist, artist_search.strip()]):
        genius_song = genius_obj.search_song(name_search, artist)
        if genius_song is not None and genius_song.lyrics:
            return genius_song.lyrics.strip()
    return None

def set_tags(song_info, genius_obj, directory):
    audio_file = eyed3.load(song_path(directory, song_info))
    
    if audio_file.tag is None:
        audio_file.initTag()
        
    if audio_file.tag is None:
        logger.error(f"Failed to initialize tags for {song_info['name']}")
        return

    cover_photo_path = directory + COVER_PHOTO
    if os.path.exists(cover_photo_path):
        mime_type, _ = mimetypes.guess_type(cover_photo_path)
        if mime_type is None:
            mime_type = "image/jpeg"  

        with open(cover_photo_path, "rb") as img_file:
            audio_file.tag.images.set(3, img_file.read(), mime_type)
    else:
        logger.error(f"Cover photo not found at: {cover_photo_path}")

    formatted_artist_string = song_info["artist"].replace(",", ";")
    audio_file.tag.artist = formatted_artist_string
    audio_file.tag.title = song_info["name"]
    audio_file.tag.album = song_info["album"]
    year = song_info.get("year") or ""
    if year.isdigit() and int(year) > 0:
        audio_file.tag.recording_date = year

    if genius_obj is not None:
        try:
            lyrics = get_lyrics(song_info["name"], song_info["artist"], genius_obj)
            if lyrics:
                audio_file.tag.lyrics.set(lyrics)
            else:
                logger.info(f"Lyrics not found for {song_info['name']} by {song_info['artist']}")
        except Exception as e:
            logger.error(f"Error setting lyrics for {song_info['name']}: {e}")

    audio_file.tag.save()
    if os.path.exists(cover_photo_path):
        os.remove(cover_photo_path)
    
def format_artists(artist_list):
    artist_combined = ""

    for artist_in_list in artist_list:
        if artist_combined != "":
            artist_combined += ", "
        artist_combined += artist_in_list["name"]

    return artist_combined


SEARCH_RESULT_LIMIT = 3


def search_videos(query, limit=SEARCH_RESULT_LIMIT):
    options = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    with YoutubeDL(options) as search_client:
        results = search_client.extract_info(f"ytsearch{limit}:{query}", download=False)
    return (results or {}).get("entries") or []


def get_link(song_info):
    min_difference = song_info["duration"]
    best_link = ""

    try:
        search_results = search_videos(song_info["name"] + " " + song_info["artist"])
    except Exception as e:
        logger.error(f"Error getting link for {song_info['name']}: {e}")
        return best_link

    for search_result in search_results:
        duration = search_result.get("duration")
        if duration is None:
            continue
        difference = abs(int(duration * 1000) - song_info["duration"])
        if difference < min_difference:
            min_difference = difference
            best_link = search_result.get("url") or f"https://www.youtube.com/watch?v={search_result['id']}"

    return best_link


def download_image(song_info, directory):
    # Get the Cover Art
    image_url = song_info["url"]
    if not image_url:
        return
    r = requests.get(image_url, timeout=30)
    with open(directory + COVER_PHOTO, "wb") as f:
        f.write(r.content)


def download_song(given_link, song_info, downloader, directory, attempts=DOWNLOAD_ATTEMPTS):
    target = song_path(directory, song_info)
    last_error = None
    for _ in range(attempts):
        try:
            downloader.extract_info(given_link)
            os.replace(os.path.join(directory, DOWNLOADED_SONG), target)
            return
        except Exception as e:
            last_error = e
            logger.error(f"Download attempt failed for {song_info['name']}: {e}")
    raise RuntimeError(f"Could not download {song_info['name']} after {attempts} attempts") from last_error


def get_songs(playlist_link, spotify_api):
    results = spotify_api.playlist_items(playlist_link, additional_types=("track",))

    songs = results["items"]

    while results["next"]:
        try:
            results = spotify_api.next(results)
            songs.extend(results["items"])
        except StopIteration:
            return songs
    return songs

def get_eta(progressbar):
    rate = progressbar.format_dict["rate"]
    remaining = (
        (progressbar.total - progressbar.n) / rate if rate and progressbar.total else 0
    )
    return remaining


# Return formatted song data in a dictionary
def format_song_data(song):
    song = song["track"]
    images = song["album"].get("images") or []
    cover_art = images[0]["url"] if images else ""
    year = (song["album"].get("release_date") or "").split("-")[0]
    name = song["name"]
    artist = format_artists(song["artists"])
    album = song["album"]["name"]
    duration = int(song["duration_ms"])
    info_dict = {
        "name": name,
        "artist": artist,
        "album": album,
        "year": year,
        "duration": duration,
        "url": cover_art,
    }

    return info_dict


def download_playlist(playlist_url, authenticator, directory, display_bar=True, normalize_sound=True, song_number_limit=0, progress_callback=None, use_exportify=True):
    configure_error_log()
    ensure_directory_exists(directory)
    audio_downloader = create_audio_downloader(directory)
    songs = fetch_playlist_songs(playlist_url, authenticator, song_number_limit, use_exportify)
    with contextlib.ExitStack() as stack:
        filename = None if display_bar else stack.enter_context(open(os.devnull, "w"))
        playlist_progress = stack.enter_context(initialize_progress_bar(len(songs), filename))
        success_counter, failure_counter = process_songs(songs, audio_downloader, directory, authenticator, playlist_progress, filename, progress_callback)
        if normalize_sound:
            normalize_volume_levels(directory, success_counter, failure_counter, progress_callback)
    return DownloadResult(total=len(songs), success=success_counter, failure=failure_counter)

def ensure_directory_exists(directory):
    if not os.path.isdir(directory):
        Path(directory).mkdir(parents=True, exist_ok=True)

def fetch_playlist_songs(playlist_url, authenticator, song_number_limit, use_exportify=True):
    if authenticator.spotify_auth is not None:
        try:
            songs = get_songs(playlist_url, authenticator.spotify_auth)
            return songs[:song_number_limit] if song_number_limit > 0 else songs
        except (SpotifyException, SpotifyOauthError) as e:
            logger.error(f"Spotify API request failed, falling back to the public playlist view: {e}")

    track_list = spotify_embed.get_embed_track_list(playlist_url)
    if use_exportify and spotify_embed.needs_full_list(track_list, song_number_limit) and exportify.is_available():
        try:
            return exportify.get_exportify_songs(playlist_url, song_number_limit)
        except exportify.ExportifyUnavailableError as e:
            message = f"WARNING: Exportify could not export the full playlist ({e})"
            logger.warning(message)
            print(message)
    return spotify_embed.build_songs(track_list, song_number_limit)

def initialize_progress_bar(playlist_size, filename):
    return tqdm(total=playlist_size, desc="Playlist Progress", position=0, leave=False, file=filename)

def process_songs(
    songs,
    audio_downloader,
    directory,
    authenticator,
    playlist_progress,
    filename,
    progress_callback=None,
):
    success_counter, failure_counter = 0, 0
    current_song, eta = None, 0

    def report_progress(current_song, eta, working = True):
        if progress_callback:
            progress_callback(
                playlist_progress.n,
                playlist_progress.total,
                success_counter,
                failure_counter,
                current_song,
                eta,
                working,
                False,
                0,
            )

    for song in songs:
        info_dict = format_song_data(song)
        current_song = f"{info_dict['name']} by {info_dict['artist'].split(',')[0]}"
        eta = get_eta(playlist_progress)

        report_progress(current_song, eta)

        if process_single_song(
            song, audio_downloader, directory, authenticator, filename
        ):
            success_counter += 1
        else:
            failure_counter += 1

        update_progress(playlist_progress)

        report_progress(current_song, eta)

    report_progress(current_song, eta, working=False)
    return success_counter, failure_counter

def process_single_song(song, audio_downloader, directory, authenticator,filename):
    song_progress = initialize_song_progress(song, filename)
    info_dict = retrieve_song_info(song, song_progress)
    download_image(info_dict, directory)
    
    link = get_link(info_dict)
    if not link:
        logger.error(f"Failed to download {info_dict['name']}: no matching YouTube video found")
        return False
    
    if not download_and_process_song(link, info_dict, audio_downloader, directory, authenticator, song_progress):
        return False
    
    song_progress.close()
    return True

def initialize_song_progress(song, filename):
    return tqdm(total=3, desc=song["track"]["name"], position=1, leave=False, file=filename)

def retrieve_song_info(song, song_progress):
    song_progress.set_description(f"{song_progress.desc}: Formatting Information")
    song_progress.update(n=1)
    return format_song_data(song)

def download_and_process_song(link, info_dict, audio_downloader, directory, authenticator, song_progress):
    try:
        download_song_with_retry(link, info_dict, audio_downloader, directory, song_progress)
        set_song_tags(info_dict, authenticator, directory, song_progress)
        return True
    except Exception as e:
        logger.error(f"Failed to download {info_dict['name']}: {e}")
        return False

def download_song_with_retry(link, info_dict, audio_downloader, directory, song_progress):
    song_progress.set_description(f"{info_dict['name']}: Downloading Song")
    song_progress.update(n=1)
    download_song(link, info_dict, audio_downloader, directory)

def set_song_tags(info_dict, authenticator, directory, song_progress):
    song_progress.set_description(f"{info_dict['name']}: Setting Tags")
    song_progress.update(n=1)
    set_tags(info_dict, authenticator.genius_auth, directory)

def update_progress(playlist_progress):
    playlist_progress.update(n=1)

def create_audio_downloader(directory: str) -> YoutubeDL:
    return YoutubeDL(
        {
            "format": "bestaudio",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "outtmpl": directory + "/downloaded_song.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
        }
    )


def measure_mean_volume(file_path):
    command = ["ffmpeg", "-hide_banner", "-nostats", "-i", file_path, "-map", "0:a", "-af", "volumedetect", "-f", "null", "-"]
    result = run_subprocess_with_flags(command, capture_output=True, text=True)
    match = MEAN_VOLUME_PATTERN.search(result.stderr or "")
    if match is None:
        raise RuntimeError(f"Could not measure the volume of {file_path}: {(result.stderr or '').strip()[-300:]}")
    return float(match.group(1))


def normalize_file(file_path, target_dbfs=TARGET_LOUDNESS_DBFS):
    original = eyed3.load(file_path)
    mean_volume = measure_mean_volume(file_path)
    gain = target_dbfs - mean_volume if math.isfinite(mean_volume) else 0.0
    temp_path = file_path + ".normalizing.mp3"
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", file_path,
        "-map", "0:a", "-map_metadata", "-1", "-af", f"volume={gain:.2f}dB",
        "-c:a", "libmp3lame", "-b:a", NORMALIZED_BITRATE, temp_path,
    ]
    result = run_subprocess_with_flags(command, capture_output=True, text=True)
    if result.returncode != 0:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise RuntimeError(f"ffmpeg could not normalize {file_path}: {(result.stderr or '').strip()[-300:]}")

    tag = original.tag if original is not None else None
    if tag is None:
        normalized = eyed3.load(temp_path)
        normalized.initTag()
        tag = normalized.tag
    tag.comments.set(NORMALIZED_MARKER)
    tag.save(temp_path)
    os.replace(temp_path, file_path)


def normalize_volume_levels(directory: str, success_counter, failure_counter, progress_callback=None) -> None:
    if not os.path.isdir(directory):
        raise ValueError("Invalid directory")

    abs_path = os.path.abspath(directory)
    files = [f for f in sorted(os.listdir(abs_path)) if f.endswith(".mp3") and not is_song_processed(os.path.join(abs_path, f))]
    normalization_progress = tqdm(total=len(files), desc="Normalizing Sound", position=0, leave=False)
    current_file = None

    def report_progress(working):
        if progress_callback:
            eta = get_eta(normalization_progress)
            progress_callback(
                normalization_progress.n, normalization_progress.total, success_counter, failure_counter,
                current_file, eta, working, working, normalization_progress.n,
            )

    for file in files:
        current_file = file
        report_progress(True)
        try:
            normalize_file(os.path.join(abs_path, file))
        except Exception as e:
            logger.error(f"Volume normalization failed for {file}: {e}")
        normalization_progress.update(n=1)

    normalization_progress.close()
    report_progress(False)


def is_song_processed(file_path):
    try:
        audio_file = eyed3.load(file_path)
        if audio_file is None or audio_file.tag is None:
            return False
        return any(comment.text == NORMALIZED_MARKER for comment in audio_file.tag.comments)
    except Exception as e:
        logger.error(f"Error while reading tags for song: {file_path}. ERROR MESSAGE: {e}")
        return False


def run_subprocess_with_flags(cmd, **kwargs):
    if sys.platform == "win32":
        kwargs["encoding"] = "utf-8"
        kwargs["errors"] = "replace"
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(cmd, **kwargs)
