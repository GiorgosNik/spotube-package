import os
import glob
from youtubesearchpython import VideosSearch
import eyed3
import requests
import shutil
from tqdm import tqdm
import spotipy
from yt_dlp import YoutubeDL
import os
from spotipy.oauth2 import SpotifyClientCredentials
import lyricsgenius
from zipfile import ZipFile
import subprocess
from pydub import AudioSegment
import urllib.request
from platform import machine
import tarfile
import zipfile
from pathlib import Path

COVER_PHOTO = "/cover_photo.jpg"
FFMPEG_UNIX_X64 = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
FFMPEG_UNIX_ARM = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz"
FFMPEG_WINDOWS_X64 = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
FFMPEG_WINDOWS_X86 = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win32-gpl.zip"


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
    name_search = name_search.split(sep5)[0]
    genius_song = genius_obj.search_song(name_search, artist_search)
    formatted_lyrics = genius_song.lyrics.rsplit(" ", 1)[0].replace("EmbedShare", "")
    formatted_lyrics = formatted_lyrics.rsplit(" ", 1)[0] + "".join(
        [i for i in formatted_lyrics.rsplit(" ", 1)[1] if not i.isdigit()]
    )
    return formatted_lyrics


def set_tags(song_info, genius_obj, directory):
    audio_file = eyed3.load(directory + "/" + song_info["name"] + ".mp3")

    if audio_file.tag is None:
        audio_file.initTag()

    audio_file.tag.images.set(
        3, open(directory + COVER_PHOTO, "rb").read(), "image/jpeg"
    )
    formatted_artist_string = song_info["artist"].replace(",", ";")
    audio_file.tag.artist = formatted_artist_string
    audio_file.tag.title = song_info["name"]
    audio_file.tag.album = song_info["album"]
    audio_file.tag.year = song_info["year"]

    try:
        audio_file.tag.lyrics.set(
            get_lyrics(song_info["name"], song_info["artist"], genius_obj)
        )
    except Exception:
        pass

    audio_file.tag.save()
    os.remove(directory + COVER_PHOTO)


def format_artists(artist_list):
    artist_combined = ""

    for artist_in_list in artist_list:
        if artist_combined != "":
            artist_combined += ", "
        artist_combined += artist_in_list["name"]

    return artist_combined


def get_link(song_info):
    min_difference = song_info["duration"]
    video_search = VideosSearch(song_info["name"] + " " + song_info["artist"], limit=3)
    best_link = None

    for search_result in video_search.result()["result"]:
        duration_str = search_result["duration"].replace(":", " ").split()
        duration_int = int(duration_str[0]) * 60000 + int(duration_str[1]) * 1000

        if abs(duration_int - song_info["duration"]) < min_difference:
            min_difference = abs(duration_int - song_info["duration"])
            best_link = search_result["link"]

    if best_link is None:
        best_link = ""

    return best_link


def download_image(song_info, directory):
    # Get the Cover Art
    image_url = song_info["url"]
    r = requests.get(image_url)
    with open(directory + COVER_PHOTO, "wb") as f:
        f.write(r.content)


def download_song(given_link, song_info, downloader, directory):
    attempts = 0

    while attempts <= 3:
        try:
            downloader.extract_info(given_link)
            default_song_name = "/downloaded_song.mp3"

            # Overwrite the file, if it exists
            if os.path.exists(directory + "/" + song_info["name"] + ".mp3"):
                os.remove(directory + "/" + song_info["name"] + ".mp3")
            os.rename(directory + default_song_name, directory + "/" + song_info["name"] + ".mp3")
            return

        except Exception as e:  # pragma: no cover
            print(str(e))
            attempts += 1
            continue


def get_songs(playlist_link, spotify_api):
    results = spotify_api.playlist_items(playlist_link, additional_types=("track",))

    songs = results["items"]

    while results["next"]:
        results = spotify_api.next(results)
        songs.extend(results["items"])

    return songs


# Handle message delivery in UI mode
def send_message(channel, type, contents):
    if channel is not None:
        channel.put({"type": type, "contents": contents})


def get_elapsed(progressbar):
    elapsed = progressbar.format_dict["elapsed"]
    return elapsed


def get_eta(progressbar):
    rate = progressbar.format_dict["rate"]
    remaining = (
        (progressbar.total - progressbar.n) / rate if rate and progressbar.total else 0
    )
    return remaining


# Return formatted song data in a dictionary
def format_song_data(song):
    song = song["track"]
    cover_art = song["album"]["images"][0]["url"]
    year = song["album"]["release_date"].replace("-", " ").split()[0]
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


def download_playlist(
    playlist_url, tokens, channel, termination_channel, directory, display_bar=True
):
    # Set up the folder for the songs
    if not os.path.isdir(directory):
        Path(directory).mkdir(parents=True, exist_ok=True)

    audio_downloader = create_audio_downloader(directory)

    songs = get_songs(playlist_url, tokens["spotify"])

    if display_bar:
        filename = None
    else:
        filename = open(os.devnull, "w")

    # Set the tqdm progress bar
    playlist_size = len(songs)
    playlist_progress = tqdm(
        total=playlist_size,
        desc="Playlist Progress",
        position=0,
        leave=False,
        file=filename,
    )

    success_counter = 0
    failure_counter = 0

    for song in songs:
        # Set song progress bar
        song_progress = tqdm(
            total=4,
            desc=song["track"]["name"],
            position=1,
            leave=False,
            file=filename,
        )

        # Retrieve Formatted Song Data
        song_progress.set_description(song_progress.desc + ": Formatting Information")
        song_progress.update(n=1)
        info_dict = format_song_data(song)

        # Download Cover Art, to preview to UI
        download_image(info_dict, directory)

        # Send Message to UI
        send_message(
            channel,
            type="song_title",
            contents="{} by {}".format(
                info_dict["name"], info_dict["artist"].split(",")[0]
            ),
        )

        # Search for the best candidate
        song_progress.set_description(info_dict["name"] + ": Selecting Best Link")
        song_progress.update(n=1)
        link = get_link(info_dict)
        if link == "":
            continue

        # Download the song
        try:
            song_progress.set_description(info_dict["name"] + ": Downloading Song")
            song_progress.update(n=1)
            download_song(link, info_dict, audio_downloader, directory)

            # Edit the ID3 Tags
            song_progress.set_description(info_dict["name"] + ": Setting Tags")
            song_progress.update(n=1)
            set_tags(info_dict, tokens["genius"], directory)

            # Move to the designated folder
            song_progress.set_description(
                info_dict["name"] + ": Moving to designated folder"
            )
            song_progress.update(n=1)
            success_counter += 1

        except Exception as e:  # pragma: no cover
            failure_counter += 1
            print(str(e))
            continue
        song_progress.close()

        # Update tqdm progress bar
        playlist_progress.update(n=1)
        send_message(
            channel,
            type="progress",
            contents=[playlist_progress.n, playlist_progress.total, success_counter, failure_counter],
        )

        elapsed = get_elapsed(playlist_progress)
        eta = get_eta(playlist_progress)
        send_message(channel, type="eta_update", contents=[elapsed, eta])

        # Check for termination message
        if not termination_channel.empty():
            message = termination_channel.get()
            if message == "EXIT":
                return

    normalize_volume_levels(directory)

    playlist_progress.close()

    send_message(channel, type="download_complete", contents=[])


def auth_handler(client_id, client_secret, genius):
    genius_auth = lyricsgenius.Genius(
        genius,
        verbose=False,
    )
    auth_manager = SpotifyClientCredentials(
        client_id=client_id, client_secret=client_secret
    )
    spotify_auth = spotipy.Spotify(auth_manager=auth_manager)

    return {"genius": genius_auth, "spotify": spotify_auth}


# Create downloader object, pass options
def create_audio_downloader(directory):
    if not ffmpeg_installed():
        audio_downloader = YoutubeDL(
            {
                "format": "bestaudio",
                "ffmpeg_location": ".",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "outtmpl": directory + "/downloaded_song.%(ext)s",
                "quiet": "true",
                "no_warnings": "true",
                "noprogress": "true",
            }
        )

    else:
        audio_downloader = YoutubeDL(
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
                "quiet": "true",
                "no_warnings": "true",
                "noprogress": "true",
            }
        )
    return audio_downloader


# Return True if ffmpeg is installed, False otherwise
def ffmpeg_installed():
    if os.name == "nt":
        # Windows
        if not os.path.exists("./ffmpeg.exe"):
            return False

    elif os.name == "posix":
        # Unix
        # Check if ffmpeg is installed
        p = str(
            subprocess.Popen(
                "which ffmpeg",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).communicate()[0]
        )
        if p == "b''" and not os.path.exists("./ffmpeg"):
            return False

    return True


# Save the state of the worker thread based on the message
def handle_message(downloader, message):
    contents = message["contents"]

    if message["type"] == "progress":
        downloader.progress = contents[0]
        downloader.total = contents[1]
        downloader.success_counter = contents[2]
        downloader.failure_counter = contents[3]

    elif message["type"] == "song_title":
        downloader.current_song = contents

    elif message["type"] == "eta_update":
        downloader.eta = contents[1]

    elif message["type"] == "download_complete":
        downloader.working = False
        downloader.progress = downloader.total


def fetch_messages(downloader):
    if not downloader.channel.empty():
        message = downloader.channel.get()
        handle_message(downloader, message)


def match_target_amplitude(sound, target_dbfs):
    change_in_dbfs = target_dbfs - sound.dBFS
    return sound.apply_gain(change_in_dbfs)


def normalize_volume_levels(directory):
    if not ffmpeg_installed():  # pragma: no cover
        print("WARNING: ffmpeg not found in PATH, volume normalization skipped.")
        return ()

    if not os.path.isdir(directory):
        raise ValueError("Invalid directory")

    abs_path = os.path.abspath(directory)

    files = os.listdir(directory)

    normalization_progress = tqdm(
        total=len(files), desc="Normalizing Sound", position=0, leave=False
    )
    for file in files:
        if file.endswith(".mp3"):
            sound = AudioSegment.from_file(abs_path + "/" + file, "mp3")
            normalized_sound = match_target_amplitude(sound, -14.0)
            normalized_sound.export(abs_path + "/" + file, format="mp3")
            normalization_progress.update(n=1)


def select_ffmpeg_link(os_type=None):
    if os_type is not None and os_type != "nt" and os_type != "posix":
        raise ValueError(
            "Invalid OS provided.\nUse:\n 'nt' for Windows, 'posix' of Unix"
        )

    if os_type is None:
        os_type = os.name

    architecture = machine().lower()

    if os_type == "nt" and architecture.find("64"):  # pragma: no cover
        url = FFMPEG_WINDOWS_X64
    elif os_type == "nt" and architecture.find("86"):  # pragma: no cover
        url = FFMPEG_WINDOWS_X86
    elif os_type == "posix" and architecture.find("arm"):  # pragma: no cover
        url = FFMPEG_UNIX_ARM
    elif os_type == "posix" and architecture == "x64":  # pragma: no cover
        url = FFMPEG_UNIX_X64
    else:  # pragma: no cover
        raise RuntimeError("Unknown OS")

    return url


def get_os_name():
    return os.name


def download_ffmpeg(os_type=None):
    if os_type is not None and os_type != "nt" and os_type != "posix":
        raise ValueError(
            "Invalid OS provided.\nUse:\n 'nt' for Windows, 'posix' of Unix"
        )

    if os_type is None:
        os_type = os.name

    url = select_ffmpeg_link(os_type)

    filename = url.split("/")[-1]

    with DownloadProgressBar(
        unit="B", unit_scale=True, miniters=1, desc=url.split("/")[-1]
    ) as t:
        urllib.request.urlretrieve(url, filename=filename, reporthook=t.update_to)

    if os_type is None:
        os_type = os.name

    if os_type == "nt":
        extract_exe_from_zip(filename)

    elif os_type == "posix":
        extract_bin_from_tarball(filename)


def extract_exe_from_zip(filename):
    with zipfile.ZipFile(filename, "r") as archive:
        files = archive.infolist()
        for file in files:
            if file.is_dir():
                continue
            if file.filename.endswith(".exe"):
                file.filename = os.path.basename(file.filename)
                archive.extract(file, "./")
    os.remove(filename)


def extract_bin_from_tarball(filename):
    with tarfile.open(filename) as archive:
        members = archive.getmembers()
        extraction_bar = tqdm(
            total=len(members), desc="Extracting files", position=1, leave=False
        )
        for member in members:
            if member.isreg() and member.name.split(".")[0] == member.name:
                member.name = os.path.basename(member.name)
                if os.getcwd() not in  os.path.realpath(member.name):
                    raise RuntimeError("Invalid tarball")
                archive.extract(member.name, ".")
            extraction_bar.update(n=1)
    os.remove(filename)


class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)

    @staticmethod
    def download_url(url, output_path):
        with DownloadProgressBar(
            unit="B", position=0, leave=False, unit_scale=True, desc=url.split("/")[-1]
        ) as t:
            urllib.request.urlretrieve(
                url, filename=output_path, reporthook=t.update_to
            )
