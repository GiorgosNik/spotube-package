import threading
import queue
from . import downloader_utils as utils
import os
import subprocess
from zipfile import ZipFile
import urllib.request
import shutil

class downloader:
    def __init__(
        self,
        spotify_client_id,
        spotify_client_secret,
        genius_api_key,
        directory="./Songs",
        display_bar=True
    ):
        # Initialise the tracking values
        self.progress = 0
        self.working = False
        self.total = None
        self.current_song = None
        self.eta = None
        self.thread = None
        self.spotify_client_id = spotify_client_id
        self.spotify_client_secret = spotify_client_secret
        self.genius_api_key = genius_api_key
        self.directory = directory
        self.display_bar = display_bar
        self.success_counter = 0
        self.fail_counter = 0

        # Set the channel that will handle the messages from the worker
        self.channel = queue.Queue()

        # Set the channel that will handle the messages from the worker
        self.termination_channel = queue.Queue()

        # Perform authentication for LyricsGenius and Spotify APIs
        self.tokens = utils.auth_handler(
            self.spotify_client_id, self.spotify_client_secret, self.genius_api_key
        )

        if not utils.ffmpeg_installed():  # pragma: no cover
            os_name = utils.get_os_name()
            utils.download_ffmpeg(os_type = os_name)

    def set_directory(self, directory):
        self.directory = directory

    def start_downloader(self, link):
        # Create a new thread to handle the download
        self.thread = threading.Thread(
            target=utils.download_playlist,
            args=[
                link,
                self.tokens,
                self.channel,
                self.termination_channel,
                self.directory,
                self.display_bar
            ],
        )
        self.working = True
        self.thread.start()

    def cancel_downloader(self):
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
        self.tokens = utils.auth_handler(
            self.spotify_client_id, self.spotify_client_secret, self.genius_api_key
        )
        if os.path.isdir(self.directory):
            shutil.rmtree(self.directory)

    def validate_playlist_url(self, playlist_url):
        try:
            self.tokens["spotify"].playlist_items(
                playlist_url, additional_types=("track",)
            )
        except Exception:
            return False
        return True

    def get_progress(self):
        utils.fetch_messages(self)
        return self.progress

    def get_total(self):
        utils.fetch_messages(self)
        return self.total

    def get_current_song(self):
        utils.fetch_messages(self)
        return self.current_song

    def get_eta(self):
        utils.fetch_messages(self)
        return self.eta

    def downloader_active(self):
        utils.fetch_messages(self)
        return self.working
    
    def get_success_counter(self):
        utils.fetch_messages(self)
        return self.success_counter
    
    def get_fail_counter(self):
        utils.fetch_messages(self)
        return self.fail_counter