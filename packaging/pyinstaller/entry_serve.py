"""PyInstaller entry: run the same stack as `jobshunt serve`."""

from __future__ import annotations

import sys


def main() -> None:
    sys.argv = ["jobshunt", "serve", *sys.argv[1:]]
    from jobshunt.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
