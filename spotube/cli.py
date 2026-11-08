import argparse
import logging
import os
import sys
from importlib.metadata import PackageNotFoundError, version

from spotube import downloader_utils as utils
from spotube import exportify, spotify_embed
from spotube.authenticator import Authenticator

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130
ENVIRONMENT_HELP = (
    "optional environment variables:\n"
    "  GENIUS_ACCESS_TOKEN       adds lyrics\n"
    "  SPOTIPY_CLIENT_ID and     read playlists through the official Spotify API\n"
    "  SPOTIPY_CLIENT_SECRET     (the account that owns the app needs Spotify Premium)\n"
    "\n"
    "Playlists over 100 tracks without API keys: install spotube[exportify], run\n"
    "'spotube login' once, and have the playlist in your Spotify library."
)


def package_version():
    try:
        return version("spotube")
    except PackageNotFoundError:
        return "unknown"


def song_limit(value):
    try:
        limit = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number: {value}") from None
    if limit < 0:
        raise argparse.ArgumentTypeError("must be 0 or more")
    return limit


def build_parser():
    parser = argparse.ArgumentParser(
        prog="spotube",
        description="Download Spotify playlists as tagged MP3 files.",
        epilog=ENVIRONMENT_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {package_version()}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")

    commands.add_parser("login", help="sign in to Spotify for playlists over 100 tracks (needed once)")

    download = commands.add_parser(
        "download", help="download a playlist", epilog=ENVIRONMENT_HELP, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    download.add_argument("url", help="Spotify playlist link")
    download.add_argument("-o", "--output", default="Songs", help="folder to save the songs in (default: %(default)s)")
    download.add_argument("-n", "--limit", type=song_limit, default=0, help="only download the first N songs")
    download.add_argument("--no-normalize", action="store_true", help="skip volume normalization")
    download.add_argument("--no-exportify", action="store_true", help="never use Exportify, even for playlists over 100 tracks")
    return parser


def print_error(message):
    print(f"spotube: {message}", file=sys.stderr)


def run_login(args):
    print("A browser window will open. Sign in to Spotify and allow Exportify access; the window closes by itself.")
    try:
        exportify.login()
    except exportify.ExportifyUnavailableError as e:
        print_error(f"login failed: {e}")
        return EXIT_FAILURE
    print("Logged in. Playlists over 100 tracks in your library will now download in full.")
    return EXIT_OK


def run_download(args):
    try:
        spotify_embed.parse_playlist_id(args.url)
    except spotify_embed.PlaylistUnavailableError as e:
        print_error(str(e))
        return EXIT_USAGE
    if not utils.ffmpeg_installed():
        print_error(utils.FFMPEG_MISSING_MESSAGE)
        return EXIT_FAILURE

    authenticator = Authenticator(
        os.environ.get("SPOTIPY_CLIENT_ID"), os.environ.get("SPOTIPY_CLIENT_SECRET"), os.environ.get("GENIUS_ACCESS_TOKEN")
    )
    try:
        result = utils.download_playlist(
            args.url,
            authenticator,
            args.output,
            display_bar=True,
            normalize_sound=not args.no_normalize,
            song_number_limit=args.limit,
            use_exportify=not args.no_exportify,
        )
    except KeyboardInterrupt:
        utils.remove_partial_files(args.output)
        print_error("cancelled, songs that finished downloading were kept")
        return EXIT_INTERRUPTED
    except Exception as e:
        logger.exception("Download failed")
        print_error(f"download failed: {e}")
        return EXIT_FAILURE

    if result.total == 0:
        print("The playlist has no downloadable songs.")
        return EXIT_OK
    print(f"Downloaded {result.success} of {result.total} songs to {os.path.abspath(args.output)}")
    if result.failure:
        print_error(f"{result.failure} song(s) failed, details are in {os.path.abspath(utils.ERROR_LOG)}")
        return EXIT_FAILURE
    return EXIT_OK


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "login":
        return run_login(args)
    return run_download(args)


if __name__ == "__main__":
    sys.exit(main())
