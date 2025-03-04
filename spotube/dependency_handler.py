import os
from tqdm import tqdm
import subprocess
import urllib.request
from platform import machine
import tarfile
import zipfile
from spotube.progress_bar import ProgressBar
import shutil

FFMPEG_UNIX_X64 = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
FFMPEG_UNIX_ARM = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz"
FFMPEG_WINDOWS_X64 = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
FFMPEG_WINDOWS_X86 = "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win32-gpl.zip"

class DependencyHandler:

    @staticmethod
    def ffmpeg_installed():
        if os.name == "nt":
            # Windows
            if not (os.path.exists("./ffmpeg.exe") or shutil.which("ffmpeg")):
                return False

        elif os.name == "posix":
            # Unix
            # Check if ffmpeg is installed
            p = str(
                subprocess.Popen(
                    "which ffmpeg",
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                ).communicate()[0]
            )
            if p == "b''" and not os.path.exists("./ffmpeg"):
                return False

        return True

    @staticmethod
    def select_ffmpeg_link(os_type=None):
        if os_type is not None and os_type != "nt" and os_type != "posix":
            raise ValueError(
                "Invalid OS provided.\nUse:\n 'nt' for Windows, 'posix' of Unix"
            )

        if os_type is None:
            os_type = os.name

        architecture = machine().lower()

        if os_type == "nt" and architecture.find("64"):  # pragma: no cover
            url = FFMPEG_WINDOWS_X64
        elif os_type == "nt" and architecture.find("86"):  # pragma: no cover
            url = FFMPEG_WINDOWS_X86
        elif os_type == "posix" and architecture.find("arm"):  # pragma: no cover
            url = FFMPEG_UNIX_ARM
        elif os_type == "posix" and architecture == "x64":  # pragma: no cover
            url = FFMPEG_UNIX_X64
        else:  # pragma: no cover
            raise RuntimeError("Unknown OS")

        return url

    @staticmethod
    def download_ffmpeg(os_type=None):
        if os_type is not None and os_type != "nt" and os_type != "posix":
            raise ValueError(
                "Invalid OS provided.\nUse:\n 'nt' for Windows, 'posix' of Unix"
            )

        if os_type is None:
            os_type = os.name

        url = DependencyHandler.select_ffmpeg_link(os_type)

        filename = url.split("/")[-1]

        with ProgressBar(
            unit="B", unit_scale=True, miniters=1, desc=url.split("/")[-1]
        ) as hook:
            urllib.request.urlretrieve(url, filename=filename, reporthook=hook.update_to)

        if os_type is None:
            os_type = os.name

        if os_type == "nt":
            DependencyHandler.extract_exe_from_zip(filename)

        elif os_type == "posix":
            DependencyHandler.extract_bin_from_tarball(filename)


    @staticmethod
    def extract_exe_from_zip(filename):
        with zipfile.ZipFile(filename, "r") as archive:
            files = archive.infolist()
            for file in files:
                if file.is_dir():
                    continue
                if file.filename.endswith(".exe"):
                    file.filename = os.path.basename(file.filename)
                    archive.extract(file, "./")
        os.remove(filename)

    @staticmethod
    def extract_bin_from_tarball(filename):
        target_dir = "."
        with tarfile.open(filename) as archive:
            members = archive.getmembers()
            extraction_bar = tqdm(
                total=len(members), desc="Extracting files", position=1, leave=False
            )
            for member in members:
                if member.isreg() and member.name.split(".")[0] == member.name:
                    member.name = os.path.basename(member.name)
                    target_path = os.path.join(target_dir, member.name)
                    target_path = os.path.normpath(target_path)
                    if os.path.commonprefix([os.path.abspath(target_dir), os.path.abspath(target_path)]) != os.path.abspath(target_dir):
                        raise RuntimeError("Invalid tarball: path traversal attempt detected")
                    with archive.extractfile(member) as source:
                        with open(target_path, 'wb') as target:
                            target.write(source.read())
                extraction_bar.update(n=1)
        os.remove(filename)
