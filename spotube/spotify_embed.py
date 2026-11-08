import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

import requests

logger = logging.getLogger(__name__)

EMBED_URL = "https://open.spotify.com/embed/{kind}/{item_id}"
DEEZER_SEARCH_URL = "https://api.deezer.com/search"
EMBED_TRACK_LIMIT = 100
ALBUM_MATCH_TOLERANCE_MS = 3000
REQUEST_TIMEOUT = 20
MAX_WORKERS = 8
HEADERS = {"User-Agent": "spotube"}

PLAYLIST_ID_PATTERN = re.compile(r"playlist[/:]([A-Za-z0-9]{22})")
NEXT_DATA_PATTERN = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


class PlaylistUnavailableError(Exception):
    pass


def parse_playlist_id(playlist_url):
    match = PLAYLIST_ID_PATTERN.search(playlist_url or "")
    if match is None:
        raise PlaylistUnavailableError(f"Not a Spotify playlist link: {playlist_url}")
    return match.group(1)


def fetch_embed_entity(kind, item_id):
    response = requests.get(EMBED_URL.format(kind=kind, item_id=item_id), headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    match = NEXT_DATA_PATTERN.search(response.text)
    if match is None:
        raise PlaylistUnavailableError(f"Unexpected Spotify embed page for {kind} {item_id}")
    page_props = json.loads(match.group(1)).get("props", {}).get("pageProps", {})
    entity = ((page_props.get("state") or {}).get("data") or {}).get("entity")
    if not entity:
        raise PlaylistUnavailableError(f"Spotify {kind} {item_id} is unavailable (status {page_props.get('status')})")
    return entity


def lookup_album_name(title, artist, duration_ms):
    try:
        response = requests.get(DEEZER_SEARCH_URL, params={"q": f"{artist} {title}", "limit": 5}, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        results = response.json().get("data") or []
    except (requests.RequestException, ValueError) as e:
        logger.error(f"Album lookup failed for {title} by {artist}: {e}")
        return ""

    for result in results:
        same_artist = (result.get("artist") or {}).get("name", "").casefold() == artist.casefold()
        close_duration = abs((result.get("duration") or 0) * 1000 - duration_ms) <= ALBUM_MATCH_TOLERANCE_MS
        if same_artist and close_duration:
            return (result.get("album") or {}).get("title", "")
    return ""


def largest_image_url(images):
    if not images:
        return ""
    return max(images, key=lambda image: image.get("maxWidth") or 0).get("url", "")


def build_song(playlist_item):
    track_id = playlist_item["uri"].rsplit(":", 1)[-1]
    name = playlist_item.get("title", "")
    artists = [{"name": artist.strip()} for artist in playlist_item.get("subtitle", "").split(",") if artist.strip()]
    duration_ms = int(playlist_item.get("duration") or 0)
    release_date = ""
    cover_url = ""

    try:
        details = fetch_embed_entity("track", track_id)
        name = details.get("name") or details.get("title") or name
        artists = [{"name": artist["name"]} for artist in details.get("artists") or []] or artists
        duration_ms = int(details.get("duration") or duration_ms)
        release_date = ((details.get("releaseDate") or {}).get("isoString") or "")[:10]
        cover_url = largest_image_url((details.get("visualIdentity") or {}).get("image"))
    except (requests.RequestException, PlaylistUnavailableError, ValueError) as e:
        logger.error(f"Could not load details for track {track_id}, using playlist data only: {e}")

    primary_artist = artists[0]["name"] if artists else ""
    return {
        "track": {
            "name": name,
            "artists": artists,
            "duration_ms": duration_ms,
            "album": {
                "name": lookup_album_name(name, primary_artist, duration_ms),
                "release_date": release_date,
                "images": [{"url": cover_url}] if cover_url else [],
            },
        }
    }


def fetch_cover_url(track_uri):
    if not (track_uri or "").startswith("spotify:track:"):
        return ""
    try:
        details = fetch_embed_entity("track", track_uri.rsplit(":", 1)[-1])
    except (requests.RequestException, PlaylistUnavailableError, ValueError) as e:
        logger.error(f"Could not load cover art for {track_uri}: {e}")
        return ""
    return largest_image_url((details.get("visualIdentity") or {}).get("image"))


def get_embed_track_list(playlist_url):
    entity = fetch_embed_entity("playlist", parse_playlist_id(playlist_url))
    return entity.get("trackList") or []


def needs_full_list(track_list, song_number_limit=0):
    return len(track_list) >= EMBED_TRACK_LIMIT and not 0 < song_number_limit <= len(track_list)


def build_songs(track_list, song_number_limit=0):
    if needs_full_list(track_list, song_number_limit):
        message = (
            f"WARNING: Spotify's public playlist view returns at most {EMBED_TRACK_LIMIT} tracks, "
            "so this playlist may be truncated. To download all of it, provide Spotify API credentials, "
            "or install spotube[exportify] and keep the playlist in your Spotify library."
        )
        logger.warning(message)
        print(message)

    track_list = [item for item in track_list if item.get("uri", "").startswith("spotify:track:")]
    if song_number_limit > 0:
        track_list = track_list[:song_number_limit]

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        return list(pool.map(build_song, track_list))


def get_embed_songs(playlist_url, song_number_limit=0):
    return build_songs(get_embed_track_list(playlist_url), song_number_limit)
