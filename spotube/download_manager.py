import ctypes
import threading
import queue
from . import downloader_utils as utils
import os
import shutil
from spotube.authenticator import Authenticator
from spotube.dependency_handler import DependencyHandler


class DownloadManager:
    def __init__(
        self,
        spotify_client_id: str,
        spotify_client_secret: str,
        genius_api_key: str,
        directory: str = "./Songs",
        display_bar: bool = True,
        normalize_sound: bool = True,
        song_number_limit: int = 0,
    ) -> None:

        # Initialise the tracking values
        self.progress = 0
        self.working = False
        self.total = 0
        self.current_song = None
        self.eta = None
        self.thread = None
        self.spotify_client_id = spotify_client_id
        self.spotify_client_secret = spotify_client_secret
        self.genius_api_key = genius_api_key
        self.directory = directory
        self.display_bar = display_bar
        self.normalize_sound = normalize_sound
        self.success_counter = 0
        self.fail_counter = 0
        self.normalizing = False
        self.normalized_songs = 0
        self.song_number_limit = song_number_limit

        # Set the channel that will handle the messages from the worker
        self.channel = queue.Queue()

        # Set the channel that will handle the messages from the worker
        self.termination_channel = queue.Queue()

        self.authenticator = Authenticator(
            spotify_client_id, spotify_client_secret, genius_api_key
        )

        if not DependencyHandler.ffmpeg_installed():  # pragma: no cover
            DependencyHandler.download_ffmpeg(os_type=os.name)

    def update_progress(
        self,
        progress: int,
        total: int,
        success_counter: int,
        failure_counter: int,
        current_song: str,
        eta: str,
        downloader_active: bool,
        normalizing: bool,
        normalized_songs: int,
    ) -> None:
        self.progress = progress
        self.total = total
        self.success_counter = success_counter
        self.failure_counter = failure_counter
        self.current_song = current_song
        self.eta = eta
        self.working = downloader_active
        self.normalizing = normalizing
        self.normalized_songs = normalized_songs

    def set_directory(self, directory: str) -> None:
        self.directory = directory

    def start_downloader(self, link: str) -> None:
        # Create a new thread to handle the download
        self.thread = threading.Thread(
            target=utils.download_playlist,
            args=(
                link,
                self.authenticator,
                self.termination_channel,
                self.directory,
                self.display_bar,
                self.normalize_sound,
                self.song_number_limit,
                lambda progress, total, success_counter, failure_counter, current_song, eta, downloader_active, normalizing, normalized_songs: self.update_progress(
                    progress,
                    total,
                    success_counter,
                    failure_counter,
                    current_song,
                    eta,
                    downloader_active,
                    normalizing,
                    normalized_songs
                ),
            ),
        )
        self.working = True
        self.thread.start()

    def cancel_downloader(self) -> None:
        self.termination_channel.put("EXIT")

        # Kill Thread
        if not self.thread.is_alive():
            return
        tid = ctypes.c_long(self.thread.ident)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            tid, ctypes.py_object(SystemExit)
        )
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
            raise RuntimeError("Failed to kill thread")

        self.working = False
        self.progress = 0
        self.total = None
        self.current_song = None
        self.eta = None
        self.thread = None
        self.channel = queue.Queue()
        self.termination_channel = queue.Queue()
        self.success_counter = 0
        self.fail_counter = 0
        self.normalizing = False
        self.normalized_songs = 0

        if os.path.isdir(self.directory):
            shutil.rmtree(self.directory)

    def validate_playlist_url(self, playlist_url: str) -> bool:
        try:
            self.authenticator.spotify_auth.playlist_items(
                playlist_url, additional_types=("track",)
            )
        except Exception:
            return False
        return True
