from __future__ import annotations

import os
import webbrowser
from typing import Optional

import click
import uvicorn

from jobshunt import __version__
from jobshunt.config import load_config
from jobshunt.paths import config_path, data_root


@click.group()
@click.version_option(__version__, prog_name="jobshunt")
def main() -> None:
    pass


@main.command("serve")
@click.option("--host", default=None, help="Override config http.host")
@click.option("--port", default=None, type=int, help="Override config http.port")
def serve_cmd(host: Optional[str], port: Optional[int]) -> None:
    c = load_config()
    h = c.http.host
    p = c.http.port
    if host:
        h = host
    if port is not None:
        p = port
    webbrowser.open(f"http://{h}:{p}/agents/jobshunt")
    uvicorn.run(
        "jobshunt.app:app",
        host=h,
        port=p,
        reload=False,
        factory=False,
    )


@main.command("config-path")
def config_path_cmd() -> None:
    click.echo(str(config_path()))


@main.command("data-path")
def data_path_cmd() -> None:
    click.echo(str(data_root()))


if __name__ == "__main__":
    main()
