#!/usr/bin/env python
import datetime
import pathlib
import re
import shutil
import tempfile
import time
from typing import Any, Iterable, List
from urllib.parse import urlparse

from loguru import logger
from pywebcopy import save_webpage

DOWNLOAD_DIR_ROOT = pathlib.Path(__file__).parents[1].joinpath("downloaded-webpages")


def _is_folder_empty(folder: pathlib.Path) -> bool:
    return list(folder.glob("*")) == []


def download_webpage(
    url: str,
    download_folder: pathlib.Path,
    bypass_robots: bool = True,
    project_name: str = "download-zillow-listings",
    open_in_browser: bool = False,
    **kwargs,
):
    """
    Download a webpage.

    :param url:
        The URL of the webpage to download.
    :param download_folder:
        The folder to download the webpage to. It is created if it does not already exist.
        If the folder exists but isn't empty, raise ``FileExistsError``.
    :param bypass_robots:
        ``bypass_robots`` arg passed to ``pywebcopy.save_webpage``.
    :param project_name:
        ``project_name`` arg passed to ``pywebcopy.save_webpage``.
    :param open_in_browser:
        ``open_in_browser`` arg passed to ``pywebcopy.save_webpage``.
    :param kwargs:
        Any other keyword arguments passed to ``pywebcopy.save_webpage``.
    """
    _kwargs = {
        "bypass_robots": bypass_robots,
        "project_name": project_name,
        "open_in_browser": open_in_browser,
    }
    _kwargs.update(kwargs)
    download_folder_abs_path = download_folder.absolute()
    if download_folder_abs_path.exists() and not _is_folder_empty(
        download_folder_abs_path
    ):
        raise FileExistsError(
            f"Cannot download to a non-empty directory, '{download_folder}'."
        )
    download_folder.mkdir(exist_ok=True, parents=True)
    save_webpage(url, str(download_folder_abs_path), **kwargs)


class ZillowUrl:
    """
    A listing on Zillow has the following url:

    https://www.zillow.com/homedetails/{street address}/{numerical code}_zpid/

    where ``street address`` is a hyphenated street address and ``numerical code``
    is an eight-digit code. For example,
    https://www.zillow.com/homedetails/123-Fake-St-Emerald-City-MO-01234/12345678_zpid/
    """

    def __init__(self, url: str) -> None:
        parsed_url = urlparse(url)
        match_result = re.search(r"homedetails/(.*)/(\d+)_zpid", parsed_url.path)
        if not match_result:
            raise ValueError(f"Invalid Zillow URL: {url}.")
        self._url = parsed_url.geturl()
        self._address = match_result.group(1)
        self._zpid = int(match_result.group(2))

    @property
    def url(self) -> str:
        """The url of the Zillow listing."""
        return self._url

    @property
    def address(self) -> str:
        """The hyphen-separated street address associated with the listing."""
        return self._address

    @property
    def zpid(self) -> int:
        """The eight-digit code that precedes the "_zpid" in the URL."""
        return self._zpid

    def __hash__(self) -> int:
        return hash(
            (
                self.url,
                self.zpid,
                self.address,
                self.__class__,
            )
        )

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False

        return all(
            (
                self.url == other.url,
                self.zpid == other.zpid,
                self.address == other.address,
            )
        )


class MissingIndexHtml(Exception):
    """Raised when the ``index.html`` file of a downloaded Zillow listing cannot be found."""

    def __init__(
        self, *args, expected_index_html: pathlib.Path, url: ZillowUrl
    ) -> None:
        self.expected_index_html = expected_index_html
        self.url = url
        super().__init__(*args)


def download_one_zillow_listing(
    url: ZillowUrl, download_dir: pathlib.Path
) -> pathlib.Path:
    """
    Download one Zillow listing.

    :param url:
        The URL of the Zillow listing.
    :param download_dir:
        Directory to download the files to. See ``main`` function docstring for
        details on the resulting directory structure.
    :return:
        The path to the ``index.html`` file downloaded. View this in the browser
        to see the listing.
    """
    download_dir.mkdir(exist_ok=True, parents=True)
    download_webpage(url.url, download_folder=download_dir)
    downloaded_index_html_path = download_dir.joinpath(
        "https_www.zillow.com",
        "www.zillow.com",
        "homedetails",
        url.address,
        f"{url.zpid}_zpid",
        "index.html",
    )
    if not downloaded_index_html_path.exists():
        raise MissingIndexHtml(
            f"Did not download index.html file at {downloaded_index_html_path}",
            expected_index_html=downloaded_index_html_path,
            url=url,
        )
    return downloaded_index_html_path


def download_multiple_zillow_listings(
    urls: List[ZillowUrl],
    download_dir_root: pathlib.Path = DOWNLOAD_DIR_ROOT,
    interval_between_downloads: int = 3,
) -> None:
    """
    Download Zillow listings.

    :param urls:
        The urls to download.
    :param download_dir_root:
        The folder to download them to. See ``main`` function for a description of the
        resulting directory structure.
    :param interval_between_downloads:
        Number of seconds to pause between downloads. Hopefully this prevents Zillow from rate-limiting
        downloads.
    """

    error_urls = []  # type: List[MissingIndexHtml]
    for url in urls:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            try:
                tmp_index_html_path = download_one_zillow_listing(
                    url, pathlib.Path(tmpdir)
                )
            except MissingIndexHtml as exc:
                error_urls.append(exc)
            else:
                listing_dir = download_dir_root.joinpath(url.address)
                listing_dir.mkdir(parents=True)
                index_html_path = shutil.copy(tmp_index_html_path, listing_dir)
                logger.info(
                    "Downloaded {} to {}",
                    url.url,
                    pathlib.Path(index_html_path).relative_to(download_dir_root.parent),
                )
                time.sleep(interval_between_downloads)

    if len(error_urls) > 0:
        logger.error(
            "The following URLs could not be downloaded: {}",
            ", ".join(map(lambda err: err.url.address, error_urls)),
        )


def filter_urls(
    urls_to_filter: List[str], download_dir_root: pathlib.Path
) -> List[ZillowUrl]:
    """Remove urls that have already been downloaded to ``download_dir_root``."""
    already_downloaded_folders = download_dir_root.glob("*")
    already_downloaded_addresses = {
        path.name.strip("/") for path in already_downloaded_folders if path.is_dir()
    }
    parsed_urls = {ZillowUrl(url) for url in urls_to_filter}
    map_street_address_to_url = {url.address: url for url in parsed_urls}
    urls_not_already_downloaded = set(map_street_address_to_url).difference(
        already_downloaded_addresses
    )
    return [
        map_street_address_to_url[address] for address in urls_not_already_downloaded
    ]


def configure_logging(log_dir_root: pathlib.Path) -> None:
    now = datetime.datetime.now()
    log_file = log_dir_root.joinpath(
        str(now.year),
        str(now.month),
        str(now.day),
        str(now.hour),
        str(now.minute),
        str(now.second),
        "log.log",
    )
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(log_file, level="TRACE")
    logger.info("Logging configured. Logs will be written to stderr and {}", log_file)


def main(
    urls: Iterable[str], download_dir_root: pathlib.Path = DOWNLOAD_DIR_ROOT
) -> None:
    """
    Entrypoint function to the application.

    :param urls:
        A list of URLs to download. If they've already been downloaded to ``download_dir_root``,
        skip their download.
    :param download_dir_root:
        The directory to download all Zillow listings. Zillow listings are saved to
        ``{download_dir_root}/{listing street address}/index.html``.
    """
    configure_logging(download_dir_root.joinpath("logs"))
    urls_not_yet_downloaded = filter_urls(list(urls), download_dir_root)
    download_multiple_zillow_listings(urls_not_yet_downloaded, download_dir_root)


if __name__ == "__main__":
    _urls_to_download = []  # put the URLS here
    main(_urls_to_download)
