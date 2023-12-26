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
        song_number_limit: int = 0
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

    def set_directory(self, directory: str) -> None:
        self.directory = directory

    def start_downloader(self, link: str) -> None:
        # Create a new thread to handle the download
        self.thread = threading.Thread(
            target=utils.download_playlist,
            args=[
                link,
                self.authenticator,
                self.channel,
                self.termination_channel,
                self.directory,
                self.display_bar,
                self.normalize_sound,
                self.song_number_limit
            ],
        )
        self.working = True
        self.thread.start()

    def cancel_downloader(self) -> None:
        self.termination_channel.put("EXIT")

        # Wait for thread to exit
        if self.thread is not None:
            self.thread.join()

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

        if os.path.isdir(self.directory):
            shutil.rmtree(self.directory)

    def validate_playlist_url(self, playlist_url:str) -> bool:
        try:
            self.authenticator.spotify_auth.playlist_items(
                playlist_url, additional_types=("track",)
            )
        except Exception:
            return False
        return True

    def get_progress(self) -> int:
        self.__fetch_messages()
        return self.progress

    def get_total(self) -> int:
        self.__fetch_messages()
        return self.total

    def get_current_song(self) -> str:
        self.__fetch_messages()
        return self.current_song

    def get_eta(self) -> int:
        self.__fetch_messages()
        return self.eta

    def downloader_active(self) -> bool:
        self.__fetch_messages()
        return self.working

    def get_success_counter(self) -> int:
        self.__fetch_messages()
        return self.success_counter

    def get_fail_counter(self) -> int:
        self.__fetch_messages()
        return self.fail_counter
    
    def __fetch_messages(self) -> None:
        if not self.channel.empty():
            message: str = self.channel.get()
            self.__handle_message(message)

    # Save the state of the worker thread based on the message
    def __handle_message(self, message: [str]) -> None:
        contents = message["contents"]

        if message["type"] == "progress":
            self.progress = contents[0]
            self.total = contents[1]
            self.success_counter = contents[2]
            self.failure_counter = contents[3]

        elif message["type"] == "song_title":
            self.current_song = contents

        elif message["type"] == "eta_update":
            self.eta = contents[1]

        elif message["type"] == "download_complete":
            self.working = False
            self.progress = self.total
