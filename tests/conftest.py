import shutil

import pytest


def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", help="run tests that call real external services")


def pytest_collection_modifyitems(config, items):
    run_live = config.getoption("--live")
    has_ffmpeg = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
    skip_live = pytest.mark.skip(reason="live test, run with --live")
    skip_ffmpeg = pytest.mark.skip(reason="ffmpeg is not installed")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(pytest.mark.enable_socket)
            if not run_live:
                item.add_marker(skip_live)
        if "ffmpeg" in item.keywords and not has_ffmpeg:
            item.add_marker(skip_ffmpeg)
