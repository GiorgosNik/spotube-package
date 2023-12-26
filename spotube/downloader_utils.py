import os
from youtubesearchpython import VideosSearch
import eyed3
import requests
from tqdm import tqdm
from yt_dlp import YoutubeDL
import os
from pydub import AudioSegment
from pathlib import Path
from spotube.dependency_handler import DependencyHandler

COVER_PHOTO = "/cover_photo.jpg"

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
    playlist_url, authenticator, channel, termination_channel, directory, display_bar = True, normalize_sound = True, song_number_limit = 0
):
    # Set up the folder for the songs
    if not os.path.isdir(directory):
        Path(directory).mkdir(parents=True, exist_ok=True)

    audio_downloader = create_audio_downloader(directory)

    songs = get_songs(playlist_url, authenticator.spotify_auth)

    # Limit the number of songs to download
    if song_number_limit > 0:
        songs = songs[:song_number_limit]

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
            set_tags(info_dict, authenticator.genius_auth, directory)

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

    if normalize_sound:
        normalize_volume_levels(directory)

    playlist_progress.close()

    send_message(channel, type="download_complete", contents=[])

# Create downloader object, pass options
def create_audio_downloader(directory: str) -> YoutubeDL:
    if not DependencyHandler.ffmpeg_installed():
        audio_downloader: YoutubeDL = YoutubeDL(
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
        audio_downloader: YoutubeDL = YoutubeDL(
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

def match_target_amplitude(sound: AudioSegment, target_dbfs: int) -> AudioSegment:
    change_in_dbfs = target_dbfs - sound.dBFS
    return sound.apply_gain(change_in_dbfs)


def normalize_volume_levels(directory: str) -> None:
    if not DependencyHandler.ffmpeg_installed():  # pragma: no cover
        print("WARNING: ffmpeg not found in PATH, volume normalization skipped.")
        return

    if not os.path.isdir(directory):
        raise ValueError("Invalid directory")

    abs_path: str = os.path.abspath(directory)

    files:[str] = os.listdir(directory)

    normalization_progress: tqdm = tqdm(
        total=len(files), desc="Normalizing Sound", position=0, leave=False
    )
    for file in files:
        if file.endswith(".mp3"):
            sound: AudioSegment = AudioSegment.from_file(abs_path + "/" + file, "mp3")
            normalized_sound: AudioSegment = match_target_amplitude(sound, -14.0)
            normalized_sound.export(abs_path + "/" + file, format="mp3")
            normalization_progress.update(n=1)
