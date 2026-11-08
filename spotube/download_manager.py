import ctypes
import threading

from spotube import downloader_utils as utils
from spotube import exportify, spotify_embed
from spotube.authenticator import Authenticator

CANCEL_TIMEOUT_SECONDS = 30


class DownloadManager:
    def __init__(
        self,
        spotify_client_id: str | None = None,
        spotify_client_secret: str | None = None,
        genius_api_key: str | None = None,
        directory: str = "./Songs",
        display_bar: bool = True,
        normalize_sound: bool = True,
        song_number_limit: int = 0,
        use_exportify: bool = True,
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
        self.failure_counter = 0
        self.normalizing = False
        self.normalized_songs = 0
        self.song_number_limit = song_number_limit
        self.use_exportify = use_exportify

        self.authenticator = Authenticator(
            spotify_client_id, spotify_client_secret, genius_api_key
        )

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
        if not utils.ffmpeg_installed():
            raise utils.FFmpegNotFoundError(utils.FFMPEG_MISSING_MESSAGE)
        self.thread = threading.Thread(
            target=utils.download_playlist,
            args=(
                link,
                self.authenticator,
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
            kwargs={"use_exportify": self.use_exportify},
        )
        self.working = True
        self.thread.start()

    def cancel_downloader(self) -> None:
        # Kill Thread
        if self.thread is None or not self.thread.is_alive():
            return
        tid = ctypes.c_long(self.thread.ident)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
            tid, ctypes.py_object(SystemExit)
        )
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
            raise RuntimeError("Failed to kill thread")
        self.thread.join(timeout=CANCEL_TIMEOUT_SECONDS)

        self.working = False
        self.progress = 0
        self.total = None
        self.current_song = None
        self.eta = None
        self.thread = None
        self.success_counter = 0
        self.failure_counter = 0
        self.normalizing = False
        self.normalized_songs = 0

        utils.remove_partial_files(self.directory)

    def login_exportify(self) -> None:
        exportify.login()

    def validate_playlist_url(self, playlist_url: str) -> bool:
        if self.authenticator.spotify_auth is not None:
            try:
                self.authenticator.spotify_auth.playlist_items(
                    playlist_url, additional_types=("track",)
                )
                return True
            except Exception:
                pass
        try:
            spotify_embed.fetch_embed_entity("playlist", spotify_embed.parse_playlist_id(playlist_url))
        except Exception:
            return False
        return True
