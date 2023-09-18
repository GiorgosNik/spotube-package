import lyricsgenius
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


class Authenticator:
    def __init__(
        self,
        spotify_client_id,
        spotify_client_secret,
        genius_api_key,
    ):
        # Initialise the tracking values
        self.genius_auth = self.authenticate_genius(genius_api_key)
        self.spotify_auth = self.authenticate_spotify(
            spotify_client_id, spotify_client_secret
        )

    def authenticate_genius(self, genius_api_key):
        genius_auth = lyricsgenius.Genius(
            genius_api_key,
            verbose=False,
        )
        return genius_auth

    def authenticate_spotify(self, spotify_client_id, spotify_client_secret):
        auth_manager = SpotifyClientCredentials(
        client_id=spotify_client_id, client_secret=spotify_client_secret
        )
        spotify_auth = spotipy.Spotify(auth_manager=auth_manager)
        return spotify_auth