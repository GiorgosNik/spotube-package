import logging
import subprocess
import sys
from unittest.mock import MagicMock, Mock, patch

import eyed3
import pytest

from spotube import downloader_utils
from spotube.downloader_utils import (
    NORMALIZED_MARKER,
    configure_error_log,
    download_song,
    ffmpeg_installed,
    is_song_processed,
    measure_mean_volume,
    normalize_file,
    normalize_volume_levels,
)

SONG = {"name": "Test Song", "artist": "Artist", "album": "Album", "year": "2020", "duration": 1000, "url": ""}


class TestDownloadSong:
    def test_moves_download_to_song_name_and_overwrites(self, tmp_path):
        (tmp_path / "Artist - Test Song.mp3").write_bytes(b"old")
        downloader = Mock()
        downloader.extract_info.side_effect = lambda link: (tmp_path / "downloaded_song.mp3").write_bytes(b"new")

        download_song("https://youtu.be/x", SONG, downloader, str(tmp_path))

        assert (tmp_path / "Artist - Test Song.mp3").read_bytes() == b"new"
        assert not (tmp_path / "downloaded_song.mp3").exists()

    def test_retries_then_raises(self, tmp_path):
        downloader = Mock()
        downloader.extract_info.side_effect = OSError("HTTP Error 403")

        with pytest.raises(RuntimeError, match="after 3 attempts") as error:
            download_song("https://youtu.be/x", SONG, downloader, str(tmp_path), attempts=3)

        assert downloader.extract_info.call_count == 3
        assert isinstance(error.value.__cause__, OSError)

    def test_recovers_after_a_failed_attempt(self, tmp_path):
        calls = []

        def flaky(link):
            calls.append(link)
            if len(calls) == 1:
                raise OSError("timeout")
            (tmp_path / "downloaded_song.mp3").write_bytes(b"ok")

        download_song("https://youtu.be/x", SONG, Mock(extract_info=flaky), str(tmp_path))

        assert len(calls) == 2
        assert (tmp_path / "Artist - Test Song.mp3").exists()


class TestFfmpegDetection:
    def test_needs_both_ffmpeg_and_ffprobe(self):
        with patch("spotube.downloader_utils.shutil.which", side_effect=lambda name: None if name == "ffprobe" else "/bin/ffmpeg"):
            assert ffmpeg_installed() is False
        with patch("spotube.downloader_utils.shutil.which", return_value="/bin/tool"):
            assert ffmpeg_installed() is True


class TestErrorLog:
    def test_handler_added_once_and_file_created_lazily(self, tmp_path):
        package_logger = logging.getLogger("spotube")
        saved = package_logger.handlers[:]
        package_logger.handlers.clear()
        log_path = tmp_path / "errors.log"
        try:
            configure_error_log(str(log_path))
            configure_error_log(str(log_path))
            assert len(package_logger.handlers) == 1
            assert not log_path.exists()

            logging.getLogger("spotube.downloader_utils").error("boom")
            package_logger.handlers[0].flush()
            assert "ERROR:boom" in log_path.read_text(encoding="utf-8")
        finally:
            for handler in package_logger.handlers:
                handler.close()
            package_logger.handlers[:] = saved

    def test_import_does_not_create_log_file(self, tmp_path):
        result = subprocess.run(
            [sys.executable, "-c", "import spotube, spotube.downloader_utils"], cwd=tmp_path, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        assert not (tmp_path / "errors.log").exists()


class TestMeasureVolume:
    def run_result(self, stderr):
        return Mock(stderr=stderr, returncode=0)

    def test_parses_volumedetect_output(self):
        output = "[Parsed_volumedetect_0 @ 0x1] mean_volume: -21.3 dB\n[Parsed_volumedetect_0 @ 0x1] max_volume: -3.0 dB"
        with patch("spotube.downloader_utils.run_subprocess_with_flags", return_value=self.run_result(output)):
            assert measure_mean_volume("song.mp3") == pytest.approx(-21.3)

    def test_silence_is_negative_infinity(self):
        with patch("spotube.downloader_utils.run_subprocess_with_flags", return_value=self.run_result("mean_volume: -inf dB")):
            assert measure_mean_volume("song.mp3") == float("-inf")

    def test_unparseable_output_raises(self):
        with patch("spotube.downloader_utils.run_subprocess_with_flags", return_value=self.run_result("Invalid data found")):
            with pytest.raises(RuntimeError, match="Invalid data found"):
                measure_mean_volume("song.mp3")


class TestNormalizeVolumeLevels:
    def test_invalid_directory(self, tmp_path):
        with pytest.raises(ValueError):
            normalize_volume_levels(str(tmp_path / "missing"), 0, 0)

    def test_skips_processed_files_and_reports_finish(self, tmp_path):
        for name in ("a.mp3", "b.mp3", "done.mp3", "notes.txt"):
            (tmp_path / name).write_bytes(b"x")
        callback = MagicMock()

        with patch("spotube.downloader_utils.is_song_processed", side_effect=lambda path: path.endswith("done.mp3")), \
                patch("spotube.downloader_utils.normalize_file") as mock_normalize:
            normalize_volume_levels(str(tmp_path), 2, 1, callback)

        assert [c.args[0].split("\\")[-1].split("/")[-1] for c in mock_normalize.call_args_list] == ["a.mp3", "b.mp3"]
        progress, total, success, failure, current, _, working, normalizing, normalized = callback.call_args_list[-1].args
        assert (progress, total, success, failure, current, normalized) == (2, 2, 2, 1, "b.mp3", 2)
        assert working is False
        assert normalizing is False

    def test_one_failure_does_not_stop_the_rest(self, tmp_path):
        for name in ("a.mp3", "b.mp3"):
            (tmp_path / name).write_bytes(b"x")

        with patch("spotube.downloader_utils.is_song_processed", return_value=False), \
                patch("spotube.downloader_utils.normalize_file", side_effect=[RuntimeError("corrupt"), None]) as mock_normalize:
            normalize_volume_levels(str(tmp_path), 0, 0)

        assert mock_normalize.call_count == 2

    def test_empty_directory_reports_without_crashing(self, tmp_path):
        callback = MagicMock()
        normalize_volume_levels(str(tmp_path), 0, 0, callback)

        assert callback.call_args.args[4] is None
        assert callback.call_args.args[6] is False


class TestNormalizeFileErrors:
    def test_ffmpeg_failure_raises_and_cleans_up(self, tmp_path):
        song = tmp_path / "song.mp3"
        song.write_bytes(b"x")
        temp_file = tmp_path / "song.mp3.normalizing.mp3"

        def failing_ffmpeg(command, **kwargs):
            temp_file.write_bytes(b"partial")
            return Mock(returncode=1, stderr="Conversion failed")

        with patch("spotube.downloader_utils.eyed3.load", return_value=None), \
                patch("spotube.downloader_utils.measure_mean_volume", return_value=-20.0), \
                patch("spotube.downloader_utils.run_subprocess_with_flags", side_effect=failing_ffmpeg):
            with pytest.raises(RuntimeError, match="Conversion failed"):
                normalize_file(str(song))

        assert not temp_file.exists()
        assert song.read_bytes() == b"x"


def make_tone(path, volume_db):
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-af", f"volume={volume_db}dB", "-c:a", "libmp3lame", "-b:a", "192k", str(path),
        ],
        check=True,
    )


@pytest.mark.ffmpeg
class TestNormalizeWithRealFfmpeg:
    def test_reaches_target_loudness_and_keeps_tags(self, tmp_path):
        song = tmp_path / "Tone.mp3"
        make_tone(song, -20)
        audio = eyed3.load(str(song))
        audio.initTag()
        audio.tag.title = "Tone"
        audio.tag.artist = "Artist A; Artist B"
        audio.tag.album = "Album"
        audio.tag.lyrics.set("la la la")
        audio.tag.images.set(3, b"\xff\xd8\xff\xe0fake-jpeg", "image/jpeg")
        audio.tag.save()
        before = measure_mean_volume(str(song))

        normalize_volume_levels(str(tmp_path), 1, 0)

        after = measure_mean_volume(str(song))
        assert before < -25
        assert after == pytest.approx(downloader_utils.TARGET_LOUDNESS_DBFS, abs=1.0)
        tag = eyed3.load(str(song)).tag
        assert tag.title == "Tone"
        assert tag.artist == "Artist A; Artist B"
        assert tag.album == "Album"
        assert tag.lyrics[0].text == "la la la"
        assert tag.images[0].image_data == b"\xff\xd8\xff\xe0fake-jpeg"
        assert [c.text for c in tag.comments] == [NORMALIZED_MARKER]
        assert eyed3.load(str(song)).info.bit_rate[1] == 192
        assert list(tmp_path.iterdir()) == [song]

    def test_untagged_file_is_marked_and_not_normalized_twice(self, tmp_path):
        song = tmp_path / "Plain.mp3"
        make_tone(song, -30)

        assert is_song_processed(str(song)) is False
        normalize_file(str(song))
        assert is_song_processed(str(song)) is True

        with patch("spotube.downloader_utils.normalize_file") as mock_normalize:
            normalize_volume_levels(str(tmp_path), 0, 0)
        mock_normalize.assert_not_called()


def api_song(name, artist="Artist", duration=200000):
    return {
        "track": {
            "name": name,
            "artists": [{"name": artist}],
            "duration_ms": duration,
            "album": {"name": "Album", "release_date": "2020-01-01", "images": [{"url": "https://img/cover"}]},
        }
    }


class TestDownloadPlaylistOffline:
    def run_playlist(self, tmp_path, songs, links, normalize_sound=True, tags_error=None):
        callback = MagicMock()
        downloader = Mock()
        downloader.extract_info.side_effect = lambda link: (tmp_path / "downloaded_song.mp3").write_bytes(link.encode())
        authenticator = Mock(spotify_auth=None, genius_auth=None)

        with patch("spotube.downloader_utils.configure_error_log"), \
                patch("spotube.downloader_utils.fetch_playlist_songs", return_value=songs) as mock_fetch, \
                patch("spotube.downloader_utils.create_audio_downloader", return_value=downloader), \
                patch("spotube.downloader_utils.get_link", side_effect=links), \
                patch("spotube.downloader_utils.download_image") as mock_image, \
                patch("spotube.downloader_utils.set_tags", side_effect=tags_error) as mock_tags, \
                patch("spotube.downloader_utils.normalize_volume_levels") as mock_normalize:
            self.result = downloader_utils.download_playlist(
                "https://open.spotify.com/playlist/x", authenticator, str(tmp_path), display_bar=False,
                normalize_sound=normalize_sound, song_number_limit=7, progress_callback=callback, use_exportify=False,
            )
        mock_fetch.assert_called_once_with("https://open.spotify.com/playlist/x", authenticator, 7, False)
        return callback, mock_image, mock_tags, mock_normalize

    def test_successes_and_failures_are_counted(self, tmp_path):
        songs = [api_song("Song One", "Artist A, Artist B"), api_song("Song Two")]

        callback, mock_image, mock_tags, mock_normalize = self.run_playlist(tmp_path, songs, ["https://yt/one", ""])

        assert (tmp_path / "Artist A - Song One.mp3").read_bytes() == b"https://yt/one"
        assert not (tmp_path / "Artist - Song Two.mp3").exists()
        assert mock_image.call_count == 2
        mock_tags.assert_called_once()
        assert mock_tags.call_args.args[0]["artist"] == "Artist A, Artist B"
        mock_normalize.assert_called_once_with(str(tmp_path), 1, 1, callback)
        progress, total, success, failure, current, _, working, _, _ = callback.call_args.args
        assert (progress, total, success, failure, current, working) == (2, 2, 1, 1, "Song Two by Artist", False)
        assert self.result == downloader_utils.DownloadResult(total=2, success=1, failure=1)

    def test_tagging_failure_counts_as_failure(self, tmp_path):
        callback, _, mock_tags, _ = self.run_playlist(tmp_path, [api_song("Song One")], ["https://yt/one"], tags_error=OSError("disk full"))

        mock_tags.assert_called_once()
        assert callback.call_args.args[2:4] == (0, 1)
        assert self.result == (1, 0, 1)

    def test_empty_playlist_finishes_cleanly(self, tmp_path):
        callback, _, _, mock_normalize = self.run_playlist(tmp_path, [], [], normalize_sound=False)

        mock_normalize.assert_not_called()
        progress, total, success, failure, current, _, working, _, _ = callback.call_args.args
        assert (progress, total, success, failure, current, working) == (0, 0, 0, 0, None, False)
        assert self.result == (0, 0, 0)


class TestGetSongs:
    def test_follows_pagination(self):
        api = Mock()
        api.playlist_items.return_value = {"items": [1, 2], "next": "page2"}
        api.next.side_effect = [{"items": [3], "next": "page3"}, {"items": [4], "next": None}]

        assert downloader_utils.get_songs("url", api) == [1, 2, 3, 4]
        api.playlist_items.assert_called_once_with("url", additional_types=("track",))


class TestSafeFilename:
    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("Normal Song", "Normal Song"),
            ("AC/DC Tribute", "AC-DC Tribute"),
            ("Left\Right | Center", "Left-Right - Center"),
            ("Why? Because: \"Reasons\" <3 *", "Why Because Reasons 3"),
            ("...Baby One More Time", "Baby One More Time"),
            ("Trailing dot.", "Trailing dot"),
            ("Tabs\tand\nnewlines", "Tabs and newlines"),
            ("CON", "CON_"),
            ("nul.remix", "nul.remix_"),
            ("???", "Untitled"),
            ("", "Untitled"),
            ("Café Ñandú 東京", "Café Ñandú 東京"),
        ],
    )
    def test_cleans_titles(self, title, expected):
        assert downloader_utils.safe_filename(title) == expected

    def test_long_titles_are_truncated(self):
        assert len(downloader_utils.safe_filename("x" * 400)) == downloader_utils.MAX_FILENAME_LENGTH

    def test_unsafe_title_downloads_to_safe_path(self, tmp_path):
        song = dict(SONG, name="Part 1/2: Intro?")
        downloader = Mock()
        downloader.extract_info.side_effect = lambda link: (tmp_path / "downloaded_song.mp3").write_bytes(b"audio")

        download_song("https://youtu.be/x", song, downloader, str(tmp_path))

        assert [p.name for p in tmp_path.iterdir()] == ["Artist - Part 1-2 Intro.mp3"]


class TestRemovePartialFiles:
    def test_removes_only_leftovers(self, tmp_path):
        leftovers = ["downloaded_song.webm", "downloaded_song.webm.part", "downloaded_song.mp3", "cover_photo.jpg", "Old.mp3.normalizing.mp3"]
        kept = ["Old.mp3", "New.mp3", "notes.txt"]
        for name in leftovers + kept:
            (tmp_path / name).write_bytes(b"x")

        downloader_utils.remove_partial_files(str(tmp_path))

        assert sorted(p.name for p in tmp_path.iterdir()) == sorted(kept)

    def test_missing_directory_is_ignored(self, tmp_path):
        downloader_utils.remove_partial_files(str(tmp_path / "missing"))


@pytest.mark.ffmpeg
class TestSetTagsOnRealFile:
    def tag_song(self, tmp_path, **overrides):
        song = dict(SONG, **overrides)
        make_tone(downloader_utils.song_path(str(tmp_path), song), -20)
        downloader_utils.set_tags(song, None, str(tmp_path))
        return eyed3.load(downloader_utils.song_path(str(tmp_path), song)).tag

    def test_year_is_saved(self, tmp_path):
        tag = self.tag_song(tmp_path, year="2013")

        assert str(tag.recording_date) == "2013"
        assert str(tag.getBestDate()) == "2013"

    @pytest.mark.parametrize("year", ["", "0000", "unknown"])
    def test_invalid_year_is_left_out(self, tmp_path, year):
        assert self.tag_song(tmp_path, year=year).recording_date is None

    def test_title_tag_keeps_original_characters(self, tmp_path):
        tag = self.tag_song(tmp_path, name="Part 1/2: Intro?")

        assert tag.title == "Part 1/2: Intro?"
        assert (tmp_path / "Artist - Part 1-2 Intro.mp3").exists()

    def test_year_survives_normalization(self, tmp_path):
        self.tag_song(tmp_path, year="1999")

        normalize_volume_levels(str(tmp_path), 1, 0)

        assert str(eyed3.load(downloader_utils.song_path(str(tmp_path), SONG)).tag.recording_date) == "1999"


class TestSongPath:
    @pytest.mark.parametrize(
        ("artist", "title", "expected"),
        [
            ("Daft Punk", "Get Lucky", "Daft Punk - Get Lucky.mp3"),
            ("Daft Punk, Pharrell Williams, Nile Rodgers", "Get Lucky", "Daft Punk - Get Lucky.mp3"),
            ("AC/DC", "Back In Black", "AC-DC - Back In Black.mp3"),
            ("", "No Artist", "No Artist.mp3"),
            (None, "No Artist", "No Artist.mp3"),
        ],
    )
    def test_primary_artist_prefix(self, tmp_path, artist, title, expected):
        path = downloader_utils.song_path(str(tmp_path), {"name": title, "artist": artist})
        assert path == str(tmp_path / expected)

    def test_same_title_different_artists_do_not_collide(self, tmp_path):
        first = downloader_utils.song_path(str(tmp_path), {"name": "Hello", "artist": "Adele"})
        second = downloader_utils.song_path(str(tmp_path), {"name": "Hello", "artist": "Lionel Richie"})
        assert first != second
