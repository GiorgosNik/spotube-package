# Spotube

<div align="center">

[![PyPi](https://img.shields.io/badge/-PyPi-blue.svg?logo=pypi&labelColor=555555&style=for-the-badge)](https://pypi.org/project/spotube "PyPi")
![PyPI - Downloads](https://img.shields.io/pypi/dm/spotube?color=%230f80c0&style=for-the-badge)
![Sonar Logo](https://img.shields.io/badge/Sonar%20cloud-F3702A?style=for-the-badge&logo=sonarcloud&logoColor=white)
![Sonar Quality Gate](https://img.shields.io/sonar/quality_gate/GiorgosNik_spotube-package?server=https%3A%2F%2Fsonarcloud.io&style=for-the-badge)
![Sonar Coverage](https://img.shields.io/sonar/coverage/GiorgosNik_spotube-package?label=COVERAGE&server=https%3A%2F%2Fsonarcloud.io&style=for-the-badge)
![Snyk Logo](https://img.shields.io/badge/Snyk-4C4A73?style=for-the-badge&logo=snyk&logoColor=white)
[![PyPI - License](https://img.shields.io/pypi/l/spotube?color=%23007ec6&style=for-the-badge)](LICENSE "License")
![Spotify Logo](https://img.shields.io/badge/Spotify-1ED760?&style=for-the-badge&logo=spotify&logoColor=white)
![Youtube Logo](https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white)

</div>



Spotube is a Python package that allows the user to download local `.mp3` copies of Spotify playlists, including cover art, artist information and lyrics.

## Description

The package can be used to download Spotify playlists, retrieving and pairing each song with the cover art as seen on Spotify, as well as any relevant metadata.
The user provides the link to a public Spotify playlist, optionally API keys for Spotify and Genius, and optionally the directory to save the downloaded songs.
The application will then:

- Read each song in the playlist from Spotify, including the official name, artists, release date and album cover art.
- Using the song name and artist(s), search for, and select the most relevant song video on Youtube. If possible, the application will avoid remixes, covers and video clip versions.
- Using the most relevant link, download the video in the highest possible quality, and convert to .mp3 format.
- Query the LyricsGenius API to retrieve the song lyrics, if available.
- Edit the .mp3 tags of the downloaded song to set the artist and album information, add the lyrics and set the cover art.
- Optionally, normalize the volume level of all downloaded `.mp3` files with ffmpeg, to even out volume differences between YouTube videos.

## API keys (optional)

Spotube works without any API keys, but API keys can optionally be used to enable more features:

| Keys | Effect |
|---|---|
| None | Playlist read from Spotify's public playlist view (first 100 tracks, or all tracks with the Exportify extra below), no lyrics |
| Genius token (free) | Adds lyrics |
| Spotify client ID and secret | Reads playlists of any length through the official Spotify API. Spotify requires the account that owns the app to have an active Premium subscription; if the API refuses a request, Spotube falls back to the public view automatically |

To generate keys, see [the Spotify Web API guide](https://developer.spotify.com/documentation/web-api/) and [the Genius API guide](https://docs.genius.com/). Keep keys out of your source code, for example in environment variables.

## Playlists over 100 tracks without keys

Without Spotify keys, Spotube can read playlists of any length through [Exportify](https://exportify.net), using in your installed Microsoft Edge or Google Chrome. Install the optional extra:

```
pip install spotube[exportify]
```

Sign in to Spotify once. A browser window opens; log in and allow Exportify read access. The session is remembered, so later runs happen in the background. From the command line:

```
spotube login
```

Or from Python:

```
from spotube import DownloadManager

manager = DownloadManager()
manager.login_exportify()
```

After that, playlists that hit the 100-track limit are exported through Exportify automatically. The playlist must be in your Spotify library (meaning that it is either created by you, or followed); if it is not, Spotube downloads the first 100 tracks and tells you to follow it. To turn this off, pass `--no-exportify` on the command line or `use_exportify=False` to `DownloadManager`.

## Dependencies

Spotube needs `ffmpeg` and `ffprobe` on your PATH. `start_downloader` raises `FFmpegNotFoundError` if they are missing.

| System | Command |
|---|---|
| Windows | `winget install ffmpeg` |
| macOS | `brew install ffmpeg` |
| Debian / Ubuntu | `sudo apt install ffmpeg` |

Alternatively, download a build from the [ffmpeg downloads page](https://ffmpeg.org/download.html) and add its `bin` folder to your PATH.

## Installation

To install the package using pip:

```
pip install spotube
```

## Command Line

```
spotube download "https://open.spotify.com/playlist/..."
```

Songs are saved as `Artist - Title.mp3` in `./Songs`. Options:

| Option | Effect |
|---|---|
| `-o`, `--output DIR` | Save the songs in `DIR` |
| `-n`, `--limit N` | Only download the first `N` songs |
| `--no-normalize` | Skip volume normalization |
| `--no-exportify` | Never use Exportify, even for playlists over 100 tracks |

API keys are read from the `GENIUS_ACCESS_TOKEN`, `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET` environment variables.

The exit code is `0` when every song downloaded, `1` when some failed or the download could not run, `2` for an invalid playlist link and `130` when cancelled with Ctrl+C.

## Python API

### Simple Use Case

Create a `DownloadManager` and call `start_downloader` with the link of a public Spotify playlist. The download runs in a background thread, and the songs are stored in `./Songs` by default.

Without any keys:

```
from spotube import DownloadManager

manager = DownloadManager()
manager.start_downloader("https://open.spotify.com/playlist/...")
```

With keys, read from environment variables:

```
import os
from spotube import DownloadManager

manager = DownloadManager(
    os.environ.get("SPOTIPY_CLIENT_ID"),
    os.environ.get("SPOTIPY_CLIENT_SECRET"),
    os.environ.get("GENIUS_ACCESS_TOKEN"),
)
manager.start_downloader("https://open.spotify.com/playlist/...")
```

### Download Directory

You can set the directory to download the songs to, in one of two ways:

By passing the optional argument `directory` to the constructor:

```
manager = DownloadManager(directory="./Songs")
```

By setting the directory after the object has been created:

```
manager.set_directory("./Songs")
```

### Stopping the Downloader

You can stop the download process using the `cancel_downloader` method:

```
manager.cancel_downloader()
```

This resets all download information, like the ETA and progress, and removes any half-downloaded files.

### Validate Playlist URL

You can check whether a Spotify playlist URL is valid with `validate_playlist_url`:

```
manager.validate_playlist_url("https://open.spotify.com/playlist/...")
```

This returns `True` for a valid link, `False` otherwise.

### Status Attributes
While a download runs, the manager updates the following attributes:

- `progress`: the number of songs processed.
- `total`: the total number of songs in the playlist.
- `success_counter` and `failure_counter`: songs downloaded and songs that failed.
- `current_song`: the title and main artist of the song being downloaded.
- `eta`: the estimated time remaining, in seconds.
- `working`: `True` while a download or volume normalization is in progress.
- `normalizing` and `normalized_songs`: whether volume normalization is running, and how many songs it has processed.

## Disclaimer

Spotube is aimed strictly at personal use, as per the YouTube, Spotify and LyricsGenius license agreements. Sharing the
content collected by using this application, or using it for profit is strictly prohibited. For more information, please read the LICENSE file included with this distribution.
