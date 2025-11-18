"""
Public API for the Termlit toolkit.

Termlit lets you design interactive terminal apps that can be delivered over
SSH. The surface mirrors the tiny snippet described in the README so a creator
only has to import `termlit`, call a few helper functions, and run
`termlit run app.py`.
"""

from importlib import metadata as importlib_metadata

from .session import (
    input,
    welcome,
    write,
    post,
    goodbye,
    spinner,
    upload_files,
    upload_file,
    download_cmd,
)
from .runtime import run

try:
    __version__ = importlib_metadata.version("termlit")
except importlib_metadata.PackageNotFoundError:  # pragma: no cover - fallback when uninstalled
    __version__ = "0.0.0+unknown"

__all__ = [
    "welcome",
    "input",
    "write",
    "post",
    "goodbye",
    "spinner",
    "run",
    "upload_files",
    "upload_file",
    "download_cmd",
    "__version__",
]
