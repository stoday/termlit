"""
DEPRECATED demo stub

The demo scripts have been moved to the top-level `scripts/` folder to
avoid packaging them into the `termlit` distribution. Please run the
scripts directly from the repository root, for example:

    python ./scripts/ssh_server_plain.py --fastapi-url http://127.0.0.1:8000

This module intentionally contains no runtime logic. It remains here
only to provide a helpful import-time message for older workflows.
"""

def _deprecated_notice():
    raise RuntimeError(
        "Demo scripts have been moved to './scripts/'.\n"
        "Run: python ./scripts/ssh_server_plain.py --fastapi-url http://127.0.0.1:8000"
    )

if __name__ == '__main__':
    _deprecated_notice()
