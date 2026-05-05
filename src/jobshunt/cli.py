from __future__ import annotations

import socket
import sys
import webbrowser
from typing import Optional

import click
import uvicorn

from jobshunt import __version__
from jobshunt.config import load_config
from jobshunt.paths import config_path, data_root


def _bind_ip(host: str) -> str:
    if host in ("0.0.0.0", "", "::"):
        return "0.0.0.0"
    return host


def _port_available(host: str, port: int) -> bool:
    """True if nothing appears to be bound to host:port yet."""
    ip = _bind_ip(host)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((ip, port))
        return True
    except OSError:
        return False


def _find_free_tcp_port(host: str) -> int:
    """Pick a free port (kernel-assigned) suitable for the given bind host."""
    ip = _bind_ip(host)
    probe = "127.0.0.1" if ip == "0.0.0.0" else ip
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((probe, 0))
        return int(s.getsockname()[1])


def _url_host_for_browser(bind_host: str) -> str:
    if bind_host in ("0.0.0.0", "", "::"):
        return "127.0.0.1"
    return bind_host


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
    wanted = p
    if not _port_available(h, p):
        p = _find_free_tcp_port(h)
        click.echo(
            f"Port {wanted} is already in use; starting server on port {p} instead.",
            err=True,
        )
    url_h = _url_host_for_browser(h)
    webbrowser.open(f"http://{url_h}:{p}/agents/jobshunt")
    # PyInstaller / frozen: uvicorn cannot always dynamic-import "jobshunt.app:app".
    if getattr(sys, "frozen", False):
        from jobshunt.app import app as asgi_app

        uvicorn.run(asgi_app, host=h, port=p, reload=False)
    else:
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
