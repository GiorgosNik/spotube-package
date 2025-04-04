import os
from youtubesearchpython import VideosSearch
import eyed3
import requests
from tqdm import tqdm
from yt_dlp import YoutubeDL
from pydub import AudioSegment
from pathlib import Path
from spotube.dependency_handler import DependencyHandler
import logging
import io
import mimetypes
import contextlib

class RateLimiterException(Exception):
    pass

throttling_messages = ["This content isn't available, try again later.", "Sign in to confirm you"]

# Setup logging configuration
logging.basicConfig(filename='errors.log', level=logging.ERROR,
                    format='%(asctime)s:%(levelname)s:%(message)s')

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

    if(genius_song is None):
        return None
    formatted_lyrics = genius_song.lyrics.rsplit(" ", 1)[0].replace("EmbedShare", "")
    formatted_lyrics = formatted_lyrics.rsplit(" ", 1)[0] + "".join(
        [i for i in formatted_lyrics.rsplit(" ", 1)[1] if not i.isdigit()]
    )
    return formatted_lyrics

def set_tags(song_info, genius_obj, directory):
    audio_file = eyed3.load(directory + "/" + song_info["name"] + ".mp3")
    
    if audio_file.tag is None:
        audio_file.initTag()
        
    if audio_file.tag is None:  #pragma: no cover
        logging.error(f"Failed to initialize tags for {song_info['name']}")
        return

    cover_photo_path = directory + COVER_PHOTO
    if os.path.exists(cover_photo_path):
        mime_type, _ = mimetypes.guess_type(cover_photo_path)
        if mime_type is None:
            mime_type = "image/jpeg"  

        with open(cover_photo_path, "rb") as img_file:
            audio_file.tag.images.set(3, img_file.read(), mime_type)
    else:   #pragma: no cover
        logging.error(f"Cover photo not found at: {cover_photo_path}")

    formatted_artist_string = song_info["artist"].replace(",", ";")
    audio_file.tag.artist = formatted_artist_string
    audio_file.tag.title = song_info["name"]
    audio_file.tag.album = song_info["album"]
    audio_file.tag.year = song_info["year"]

    try:
        lyrics = get_lyrics(song_info["name"], song_info["artist"], genius_obj)
        if lyrics:
            audio_file.tag.lyrics.set(lyrics)
        else:   #pragma: no cover
            logging.info(f"Lyrics not found for {song_info['name']} by {song_info['artist']}")
    except Exception as e:  #pragma: no cover
        logging.error(f"Error setting lyrics for {song_info['name']}: {e}")

    audio_file.tag.save()
    os.remove(cover_photo_path)


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

    try:
        for search_result in video_search.result()["result"]:
            duration_str = search_result["duration"].replace(":", " ").split()
            duration_int = int(duration_str[0]) * 60000 + int(duration_str[1]) * 1000

            if abs(duration_int - song_info["duration"]) < min_difference:
                min_difference = abs(duration_int - song_info["duration"])
                best_link = search_result["link"]
    except Exception as e:  # pragma: no cover
        logging.error(f"Error getting link for {song_info['name']}: {e}")

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
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                downloader.extract_info(given_link)
            stdout = stdout_buffer.getvalue()
            stderr = stderr_buffer.getvalue()

            if any(error in stdout for error in throttling_messages) or any(error in stderr for error in throttling_messages):
                raise RateLimiterException("An error occurred, please try again later.")

            default_song_name = "/downloaded_song.mp3"

            # Overwrite the file, if it exists
            if os.path.exists(directory + "/" + song_info["name"] + ".mp3"):
                os.remove(directory + "/" + song_info["name"] + ".mp3")
            os.rename(directory + default_song_name, directory + "/" + song_info["name"] + ".mp3")
            return

        except Exception as e:  # pragma: no cover
            if isinstance(e, RateLimiterException):
                raise e
            else:   #pragma: no cover
                logging.error(str(e))
                attempts += 1
                continue


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
    playlist_url, authenticator, termination_channel, directory, display_bar=True, normalize_sound=True, song_number_limit=0
, progress_callback=None):
    ensure_directory_exists(directory)
    audio_downloader = create_audio_downloader(directory)
    songs = fetch_playlist_songs(playlist_url, authenticator, song_number_limit)
    filename = None if display_bar else open(os.devnull, "w")
    playlist_progress = initialize_progress_bar(len(songs), filename)
    success_counter, failure_counter =  process_songs(songs, audio_downloader, directory, authenticator, termination_channel, playlist_progress, filename, progress_callback)
    finalize_download(playlist_progress, directory, normalize_sound, success_counter, failure_counter, progress_callback)

def ensure_directory_exists(directory):
    if not os.path.isdir(directory):
        Path(directory).mkdir(parents=True, exist_ok=True)

def fetch_playlist_songs(playlist_url, authenticator, song_number_limit):
    songs = get_songs(playlist_url, authenticator.spotify_auth)
    return songs[:song_number_limit] if song_number_limit > 0 else songs

def initialize_progress_bar(playlist_size, filename):
    return tqdm(total=playlist_size, desc="Playlist Progress", position=0, leave=False, file=filename)

def process_songs(songs, audio_downloader, directory, authenticator, termination_channel, playlist_progress, filename, progress_callback= None):
    success_counter, failure_counter = 0, 0
    
    for song in songs:
        if process_single_song(song, audio_downloader, directory, authenticator, filename):
            success_counter += 1
        else:
            failure_counter += 1
            
        update_progress(playlist_progress)
        info_dict = format_song_data(song)
        current_song = f"{info_dict['name']} by {info_dict['artist'].split(',')[0]}"
        eta = get_eta(playlist_progress)
        
        if(progress_callback):
            progress_callback(playlist_progress.n, playlist_progress.total ,success_counter, failure_counter, current_song, eta, True, False, 0)
        
        if check_termination(termination_channel):
            return success_counter, failure_counter
        
    if(progress_callback):
            progress_callback(playlist_progress.n, playlist_progress.total, success_counter, failure_counter, current_song, eta, True, False, 0)
    return success_counter, failure_counter

def process_single_song(song, audio_downloader, directory, authenticator,filename):
    song_progress = initialize_song_progress(song, filename)
    info_dict = retrieve_song_info(song, song_progress)
    download_image(info_dict, directory)
    
    link = get_link(info_dict)
    if not link:
        logging.error(f"Failed to download {info_dict['name']} after 3 attempts. Error: Could not find link")
        return False
    
    if not download_and_process_song(link, info_dict, audio_downloader, directory, authenticator, song_progress):
        return False
    
    song_progress.close()
    return True

def initialize_song_progress(song, filename):
    return tqdm(total=4, desc=song["track"]["name"], position=1, leave=False, file=filename)

def retrieve_song_info(song, song_progress):
    song_progress.set_description(f"{song_progress.desc}: Formatting Information")
    song_progress.update(n=1)
    return format_song_data(song)

def download_and_process_song(link, info_dict, audio_downloader, directory, authenticator, song_progress):
    try:
        download_song_with_retry(link, info_dict, audio_downloader, directory, song_progress)
        set_song_tags(info_dict, authenticator, directory, song_progress)
        move_song_to_folder(info_dict, song_progress)
        return True
    except Exception as e:
        logging.error(f"Failed to download {info_dict['name']} after 3 attempts. Error: {str(e)}")
        return False

def download_song_with_retry(link, info_dict, audio_downloader, directory, song_progress):
    song_progress.set_description(f"{info_dict['name']}: Downloading Song")
    song_progress.update(n=1)
    
    try:
        download_song(link, info_dict, audio_downloader, directory)
    except RateLimiterException:
        logging.error(f"Rate limiter error when downloading {info_dict['name']}")
        audio_downloader = create_audio_downloader(directory)
        download_song(link, info_dict, audio_downloader, directory)

def set_song_tags(info_dict, authenticator, directory, song_progress):
    song_progress.set_description(f"{info_dict['name']}: Setting Tags")
    song_progress.update(n=1)
    set_tags(info_dict, authenticator.genius_auth, directory)

def move_song_to_folder(info_dict, song_progress):
    song_progress.set_description(f"{info_dict['name']}: Moving to designated folder")
    song_progress.update(n=1)

def update_progress(playlist_progress):
    playlist_progress.update(n=1)

def check_termination(termination_channel):
    if not termination_channel.empty():
        return termination_channel.get() == "EXIT"
    return False

def finalize_download(playlist_progress, directory, normalize_sound, success_counter, failure_counter, progress_callback=None):
    if normalize_sound:
        normalize_volume_levels(directory, success_counter, failure_counter, progress_callback)
    playlist_progress.close()

# Create downloader object, pass options
def create_audio_downloader(directory: str) -> YoutubeDL:
    if not DependencyHandler.ffmpeg_installed(): #pragma: no cover
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

def match_target_amplitude(sound: AudioSegment, target_dbfs: float) -> AudioSegment:
    change_in_dbfs = target_dbfs - sound.dBFS
    return sound.apply_gain(change_in_dbfs)


def _restore_audio_tags(file_path: str, tags: dict) -> None:
    if tags:
        audio_file = eyed3.load(file_path)
        if audio_file.tag is None:
            audio_file.initTag()

        audio_file.tag.artist = tags.get("artist")
        audio_file.tag.title = tags.get("title")
        audio_file.tag.album = tags.get("album")
        audio_file.tag.lyrics.set(tags.get("lyrics", ""))
        
        # Restore images
        for image_path in tags.get("images", []):
            with open(image_path, "rb") as img_file:
                audio_file.tag.images.set(3, img_file.read(), "image/jpeg")
            os.remove(image_path)  # Delete image after restoration
        
        audio_file.tag.save()

def _extract_tags(audio_file) -> dict:
    if not audio_file or not audio_file.tag:
        return {"artist": "", "title": "", "album": "", "lyrics": "", "images": []}
    
    tags = {
        "artist": audio_file.tag.artist or "",
        "title": audio_file.tag.title or "",
        "album": audio_file.tag.album or "",
        "lyrics": audio_file.tag.lyrics[0].text if audio_file.tag.lyrics else "",
        "images": []
    }
    
    return tags

def _save_images(directory: str, audio_file, tags: dict) -> None:
    try:
        if not audio_file or not audio_file.tag:
            return
        
        for image in audio_file.tag.images:
            image_path = os.path.join(directory, f"{tags['artist']} - {tags['album']}({image.picture_type}).jpg")
            with open(image_path, "wb") as img_file:
                img_file.write(image.image_data)
            tags["images"].append(image_path)
    except Exception as e:  #pragma: no cover
        logging.error(f"Error saving images: {e}")

def normalize_volume_levels(directory: str, success_counter, failure_counter, progress_callback=None) -> None:
    if not DependencyHandler.ffmpeg_installed():  # pragma: no cover
        print("WARNING: ffmpeg not found in PATH, volume normalization skipped.")
        return

    if not os.path.isdir(directory):
        raise ValueError("Invalid directory")

    abs_path: str = os.path.abspath(directory)
    files: list = [f for f in os.listdir(directory) if f.endswith(".mp3")]

    normalization_progress: tqdm = tqdm(
        total=len(files), desc="Normalizing Sound", position=0, leave=False
    )
 
    processed_files = 0
    for file in files:
        if progress_callback:
            eta = get_eta(normalization_progress)
            progress_callback(normalization_progress.n, normalization_progress.total,success_counter, failure_counter, file, eta, True, True, processed_files)
                    
        file_path = os.path.join(abs_path, file)

        # Load original tags and save images
        audio_file = eyed3.load(file_path)
        tags = _extract_tags(audio_file)
        _save_images(directory, audio_file, tags)

        # Normalize audio
        sound: AudioSegment = AudioSegment.from_file(file_path, "mp3")
        normalized_sound: AudioSegment = match_target_amplitude(sound, -14.0)
        normalized_sound.export(file_path, format="mp3")

        # Restore tags
        _restore_audio_tags(file_path, tags)
        normalization_progress.update(n=1)
        processed_files += 1