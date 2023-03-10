import threading
import queue
import src.spotube.downloader_utils as utils
import os
import subprocess
from zipfile import ZipFile


class downloader:
    def __init__(
        self, spotify_id, spotify_api_key, genius_api_key, directory="./Songs"
    ):
        # Initialise the tracking values
        self.progress = 0
        self.total = None
        self.current_song = None
        self.eta = None
        self.thread = None
        self.spotify_id = spotify_id
        self.spotify_api_key = spotify_api_key
        self.genius_api_key = genius_api_key
        self.directory = directory

        # Set the channel that will handle the messages from the worker
        self.channel = queue.Queue()

        # Set the channel that will handle the messages from the worker
        self.termination_channel = queue.Queue()

        # Perform authentication for LyricsGenius and Spotify APIs
        self.tokens = utils.auth_handler(
            self.spotify_id, self.spotify_api_key, self.genius_api_key
        )

        if not utils.ffmpeg_installed():
            utils.ffmpeg_error_message()

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
            ],
        )
        self.thread.start()

    def stop_downloader(self):
        self.termination_channel.put(utils.EXIT)

        # Wait for thread to exit
        if self.thread is not None:
            self.thread.join()

        self.progress = 0
        self.total = None
        self.current_song = None
        self.eta = None
        self.thread = None
        self.channel = queue.Queue()
        self.termination_channel = queue.Queue()
        self.tokens = utils.auth_handler(
            self.spotify_id, self.spotify_api_key, self.genius_api_key
        )

    def validate_playlist_url(self, playlist_url):
        try:
            self.tokens["spotify"].playlist_tracks(playlist_url)
        except Exception as e:
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
