#!/usr/bin/env python
"""TUF Client Example"""

# Copyright 2012 - 2017, New York University and the TUF contributors
# SPDX-License-Identifier: MIT OR Apache-2.0

import logging
import os
import shutil
from pathlib import Path

import click
import requests
from tuf.api.exceptions import DownloadError, RepositoryError
from tuf.ngclient.updater import Updater
from tuf.ngclient.config import UpdaterConfig

# constants
BASE_URL = "http://127.0.0.1:8080/"
DOWNLOAD_URL = "http://localhost:8000/"
DOWNLOAD_DIR = "./client"
METADATA_DIR = f"{Path.home()}/.local/share/demo-pik"
PIK_DIR = os.path.dirname(os.path.abspath(__file__))


def _init() -> None:
    """Initialize local trusted metadata and create a directory for downloads"""

    if not os.path.isdir(DOWNLOAD_DIR):
        os.mkdir(DOWNLOAD_DIR)

    if not os.path.isdir(METADATA_DIR):
        os.makedirs(METADATA_DIR)

    if not os.path.isfile(f"{METADATA_DIR}/root.json"):
        shutil.copy(
            f"{PIK_DIR}/1.root.json", f"{METADATA_DIR}/root.json"
        )
        click.echo(f"Added trusted root in {METADATA_DIR}")

    else:
        click.echo(f"Found trusted root in {METADATA_DIR}")


def _download(target: str) -> bool:
    """
    Download the target file using ``ngclient`` Updater.

    The Updater refreshes the top-level metadata, get the target information,
    verifies if the target is already cached, and in case it is not cached,
    downloads the target file.

    Returns:
        A boolean indicating if process was successful
    """
    try:
        updater = Updater(
            metadata_dir=METADATA_DIR,
            metadata_base_url=f"{BASE_URL}/",
            target_base_url=f"{DOWNLOAD_URL}",
            target_dir=DOWNLOAD_DIR,
            config=UpdaterConfig(prefix_targets_with_hash=False),
        )
        updater.refresh()

        info = updater.get_targetinfo(target)

        if info is None:
            return False

        path = updater.find_cached_target(info)
        if path:
            click.echo(f"Target already available")
            return True

        path = updater.download_target(info)
        short_name = os.path.join(DOWNLOAD_DIR, path.split('%2F')[-1])
        os.symlink(path, short_name)
        click.echo(f"Target downloaded and available in {short_name}")

    except (OSError, RepositoryError, DownloadError) as e:
        click.echo(f"Failed to download target {target}: {e}")
        return False

    return True


@click.option(
    '-v',
    '--verbose',
    help="Output verbosity level (-v, -vv, ...)",
    count=True,
    default=0,
    required=False
)
@click.group()
def cli(verbose):

    if verbose == 0:
        loglevel = logging.ERROR
    elif verbose == 1:
        loglevel = logging.WARNING
    elif verbose == 2:
        loglevel = logging.INFO
    else:
        loglevel = logging.DEBUG

    logging.basicConfig(level=loglevel)

@click.command()
@click.argument('package_name')
def download(package_name):
    _init()
    name = package_name.split("==")[0]
    if "==" not in package_name:
        try:
            query_latest = requests.get(
                f"https://api.github.com/repos/KAPRIEN/{name}/releases/latest"
            )
        except requests.exceptions.ConnectionError() as err:
            raise click.ClickException(str(err))

        if query_latest.status_code != 200:
            raise click.ClickException(query_latest.text)
        else:
            query_data = query_latest.json()
            for asset in query_data.get("assets"):
                if (
                    asset.get("content_type") == "application/gzip"
                    or asset.get("content_type") == "application/x-gzip"
                ):
                    full_url = asset.get("browser_download_url")
                    package_to_download = "/".join(full_url.split("/")[-2:])
                    click.echo(f"Found version: {package_to_download.split('/')[0]}")
                    if not _download(package_to_download):
                        raise click.ClickException(
                            f"{package_name} not found. "
                            f"Package {package_to_download} not signed.")
                    break

    else:
        version = package_name.split("==")[1]
        package_to_download = f"v{version}/{name.replace('-', '_')}-{version}.tar.gz"
        if not _download(package_to_download):
            raise click.ClickException(f"{name} version {version} not found.")


cli.add_command(download)


if __name__ == "__main__":
    cli()
