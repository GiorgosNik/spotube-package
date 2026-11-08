import subprocess
import sys
from unittest.mock import patch

import pytest

from spotube import cli, exportify
from spotube.downloader_utils import DownloadResult

URL = "https://open.spotify.com/playlist/05MWSPxUUWA0d238WFvkKA?si=abc"


@pytest.fixture
def ffmpeg_present():
    with patch("spotube.cli.utils.ffmpeg_installed", return_value=True):
        yield


@pytest.fixture
def no_keys(monkeypatch):
    for name in ("SPOTIPY_CLIENT_ID", "SPOTIPY_CLIENT_SECRET", "GENIUS_ACCESS_TOKEN"):
        monkeypatch.delenv(name, raising=False)


def fake_download(total, success, failure):
    def run(url, authenticator, directory, **kwargs):
        return DownloadResult(total=total, success=success, failure=failure)
    return run


class TestParser:
    def test_command_is_required(self, capsys):
        with pytest.raises(SystemExit) as exit_info:
            cli.main([])
        assert exit_info.value.code == 2
        assert "command" in capsys.readouterr().err

    def test_version(self, capsys):
        with pytest.raises(SystemExit) as exit_info:
            cli.main(["--version"])
        assert exit_info.value.code == 0
        assert capsys.readouterr().out.startswith("spotube ")

    @pytest.mark.parametrize("limit", ["-1", "ten"])
    def test_invalid_limit(self, limit, capsys):
        with pytest.raises(SystemExit) as exit_info:
            cli.main(["download", URL, "--limit", limit])
        assert exit_info.value.code == 2

    def test_help_mentions_environment_variables(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["download", "--help"])
        help_text = capsys.readouterr().out
        assert "GENIUS_ACCESS_TOKEN" in help_text
        assert "spotube login" in help_text

    def test_runs_as_module(self):
        result = subprocess.run([sys.executable, "-m", "spotube", "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "download" in result.stdout and "login" in result.stdout


class TestLogin:
    @patch("spotube.cli.exportify.login")
    def test_success(self, mock_login, capsys):
        assert cli.main(["login"]) == cli.EXIT_OK
        mock_login.assert_called_once_with()
        assert "Logged in" in capsys.readouterr().out

    @patch("spotube.cli.exportify.login", side_effect=exportify.ExportifyUnavailableError("run: pip install spotube[exportify]"))
    def test_failure_is_reported(self, mock_login, capsys):
        assert cli.main(["login"]) == cli.EXIT_FAILURE
        assert "pip install spotube[exportify]" in capsys.readouterr().err


@pytest.mark.usefixtures("no_keys")
class TestDownload:
    @patch("spotube.cli.utils.download_playlist")
    def test_invalid_url_is_rejected_before_downloading(self, mock_download, capsys):
        assert cli.main(["download", "https://example.com/not-a-playlist"]) == cli.EXIT_USAGE
        mock_download.assert_not_called()
        assert "Not a Spotify playlist link" in capsys.readouterr().err

    @patch("spotube.cli.utils.download_playlist")
    def test_missing_ffmpeg(self, mock_download, capsys):
        with patch("spotube.cli.utils.ffmpeg_installed", return_value=False):
            assert cli.main(["download", URL]) == cli.EXIT_FAILURE
        mock_download.assert_not_called()
        assert "winget install ffmpeg" in capsys.readouterr().err

    @pytest.mark.usefixtures("ffmpeg_present")
    @patch("spotube.cli.Authenticator")
    def test_successful_download(self, mock_auth, capsys, tmp_path):
        output = tmp_path / "Music"
        with patch("spotube.cli.utils.download_playlist", side_effect=fake_download(12, 12, 0)) as mock_download:
            code = cli.main(["download", URL, "-o", str(output), "-n", "12", "--no-exportify"])

        assert code == cli.EXIT_OK
        mock_auth.assert_called_once_with(None, None, None)
        kwargs = mock_download.call_args.kwargs
        assert mock_download.call_args.args == (URL, mock_auth.return_value, str(output))
        assert kwargs["normalize_sound"] is True
        assert kwargs["song_number_limit"] == 12
        assert kwargs["use_exportify"] is False
        assert kwargs["display_bar"] is True
        assert f"Downloaded 12 of 12 songs to {output}" in capsys.readouterr().out

    @pytest.mark.usefixtures("ffmpeg_present")
    def test_keys_come_from_environment(self, monkeypatch):
        monkeypatch.setenv("SPOTIPY_CLIENT_ID", "id")
        monkeypatch.setenv("SPOTIPY_CLIENT_SECRET", "secret")
        monkeypatch.setenv("GENIUS_ACCESS_TOKEN", "token")
        with patch("spotube.cli.Authenticator") as mock_auth, \
                patch("spotube.cli.utils.download_playlist", side_effect=fake_download(1, 1, 0)):
            cli.main(["download", URL, "--no-normalize"])
        mock_auth.assert_called_once_with("id", "secret", "token")

    @pytest.mark.usefixtures("ffmpeg_present")
    @patch("spotube.cli.Authenticator")
    def test_failed_songs_give_nonzero_exit(self, mock_auth, capsys):
        with patch("spotube.cli.utils.download_playlist", side_effect=fake_download(5, 3, 2)):
            assert cli.main(["download", URL]) == cli.EXIT_FAILURE
        captured = capsys.readouterr()
        assert "Downloaded 3 of 5 songs" in captured.out
        assert "2 song(s) failed" in captured.err
        assert "errors.log" in captured.err

    @pytest.mark.usefixtures("ffmpeg_present")
    @patch("spotube.cli.Authenticator")
    def test_empty_playlist(self, mock_auth, capsys):
        with patch("spotube.cli.utils.download_playlist", side_effect=fake_download(0, 0, 0)):
            assert cli.main(["download", URL]) == cli.EXIT_OK
        assert "no downloadable songs" in capsys.readouterr().out

    @pytest.mark.usefixtures("ffmpeg_present")
    @patch("spotube.cli.Authenticator")
    def test_ctrl_c_cleans_up_partial_files(self, mock_auth, capsys, tmp_path):
        with patch("spotube.cli.utils.download_playlist", side_effect=KeyboardInterrupt), \
                patch("spotube.cli.utils.remove_partial_files") as mock_cleanup:
            assert cli.main(["download", URL, "-o", str(tmp_path)]) == cli.EXIT_INTERRUPTED
        mock_cleanup.assert_called_once_with(str(tmp_path))
        assert "cancelled" in capsys.readouterr().err

    @pytest.mark.usefixtures("ffmpeg_present")
    @patch("spotube.cli.Authenticator")
    def test_unexpected_error_is_reported(self, mock_auth, capsys):
        with patch("spotube.cli.utils.download_playlist", side_effect=ConnectionError("network unreachable")):
            assert cli.main(["download", URL]) == cli.EXIT_FAILURE
        assert "download failed: network unreachable" in capsys.readouterr().err
