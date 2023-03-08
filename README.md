# Spotube

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

## Obtaining API keys

For instructions on how to generate the two sets of API keys needed to run the application, please refer to:

- [The Spotify API guide](https://developer.spotify.com/documentation/web-api/)
- [The Genius API guide](https://docs.genius.com/)

## Dependencies

In order to convert the YouTube videos to `.mp3` format, you need to have ffmpeg installed in your system.
To do this, follow the instructions relevant to your system:

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

This section is under construction.

## Disclaimer

Spotube is aimed strictly at personal use, as per the YouTube, Spotify and LyricsGenius license agreements. Sharing the
content collected by using this application, or using it for profit is strictly prohibited. For more information, please read the LICENSE file included with this distribution.
