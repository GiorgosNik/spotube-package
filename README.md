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
The user provides the link to a public spotify playlist, API keys for Spotify and Genius, and, optionally the directory to save the downloaded songs.
The application will then:

- Query the Spotify API for information on each song in the playlist, including the official name, artists, album cover art etc.
- Using the song name and artist(s), search for, and select the most relevant song video on Youtube. If possible, the application will avoid remixes, covers and video clip versions.
- Using the most relevant link, download the video in the highest possible quality, and convert to .mp3 format.
- Query the LyricsGenius API to retrieve the song lyrics, if available.
- Edit the .mp3 tags of the downloaded song to set the artist and album information, add the lyrics and set the cover art.
- Optionally, normalize the volume level of all downloaded `.mp3` files, to remedy the possible volume difference of YouTube videos from one another.

## Obtaining API keys

For instructions on how to generate the two sets of API keys needed to run the application, please refer to:

- [The Spotify API guide](https://developer.spotify.com/documentation/web-api/)
- [The Genius API guide](https://docs.genius.com/)

## Dependencies

In order to utilize all the features provided by Spotube, it is necessary to have ffmpeg installed and configured in your system`s PATH variable. If no ffmpeg installation is detected, Spotube will attempt to download the [prebuilt ffmpeg binaries](https://github.com/yt-dlp/FFmpeg-Builds) kindly provided by the yt-dlp team. This will allow Spotube to function, but will disable some advanced features like volume normalization.

To install ffmpeg manually, follow the instructions relevant to your system:

### Ubuntu:

```
sudo apt install software-properties-common
sudo apt update
sudo add-apt-repository ppa:jonathonf/ffmpeg-4
sudo apt install ffmpeg
```

### Windows:

- Download ffmpeg from the [ffmpeg downloads page](https://ffmpeg.org/download.html)
- Extract the downloaded archive
- Add the directory where ffmpeg was extracted to the PATH

## Installation

To install the package using pip:

```
pip install spotube
```

## Instructions and Examples

### Simple Use Case

The simplest way to use Spotube involves creating a downloader object using the `Spotify Client ID` and `Spotify Client Secret` and the `Genius API Token`, and then calling start_downloader with the link of a Spotify Playlist as the argument. The downloaded songs will be stored in the directory `./Songs` by default.
This simple use case looks like this:

```
from spotube import downloader

SPOTIFY_ID = {YOUR SPOTIFY API CLIENT ID}
SPOTIFY_SECRET = {YOUR SPOTIFY API CLIENT SECRET}
GENIUS_TOKEN = {YOUR GENIUS API TOKEN}
PLAYLIST_LINK = {THE LINK TO A SPOTIFY PLAYLIST}

my_downloaded = downloader(SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN)

my_downloaded.start_downloader(VALID_PLAYLIST)
```

### Download Directory

You can set the directory to download the songs to, in one of two ways:

By passing the optional argument `directory` in the downloaded constructor:

```
my_downloaded = downloader(SPOTIFY_ID, SPOTIFY_SECRET, GENIUS_TOKEN, directory = "./Songs")
```

By setting the directory after the downloader object has been created:

```
my_downloaded = set_directory("./Songs")
```

### Stopping the Downloader

You can stop the download process using the `cancel_downloader` method on a downloader object:

```
my_downloader = cancel_downloader()
```

This will reset all download information, like the ETA and progress.

### Validate Playlist URL

You can examine if a Spotify playlist URL is valid by using the `validate_playlist_url` method:

```
my_downloaded = validate_playlist_url({LINK TO A PLAYLIST})
```

This method will return `True` for a valid link, `False` otherwise.

### Status Methods

The downloader class implements various methods to track the status of the downloader. These include:

- `get_progress()`: This method returns the number of songs processed.
- `get_total()`: This method returns the total number of songs in the playlist.
- `get_current_song()`: This method returns the title and artist(s) of the song currently being downloaded.
- `get_eta()`: This method returns the estimated time remaining for the download to finish, in seconds.
- `downloader_active()`: Returns `True` if there is an active download in progress, `False` otherwise.

## Disclaimer

Spotube is aimed strictly at personal use, as per the YouTube, Spotify and LyricsGenius license agreements. Sharing the
content collected by using this application, or using it for profit is strictly prohibited. For more information, please read the LICENSE file included with this distribution.
