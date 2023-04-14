import itertools
import pathlib
import shutil

import pytest

from download_zillow_listings.main import (
    MissingIndexHtml,
    ZillowUrl,
    download_multiple_zillow_listings,
    download_one_zillow_listing,
    filter_urls,
)


class TestFilterUrls:
    @staticmethod
    def test_simple(tmp_path: pathlib.Path) -> None:
        """ """
        # Arrange
        expected = [
            ZillowUrl(
                "https://www.zillow.com/homedetails/123-Fake-St-Paradise-City-MA-01234/87654321_zpid/"
            )
        ]
        urls_under_test = [
            "https://www.zillow.com/homedetails/123-Fake-St-Emerald-City-MO-01234/12345678_zpid/",
            "https://www.zillow.com/homedetails/123-Fake-St-Paradise-City-MA-01234/87654321_zpid/",
        ]
        root_download_dir = tmp_path.joinpath("root")
        root_download_dir.joinpath("123-Fake-St-Emerald-City-MO-01234").mkdir(
            parents=True
        )

        # Act
        result = filter_urls(urls_under_test, download_dir_root=root_download_dir)

        # Assert
        assert result == expected

    @staticmethod
    def test_empty_list_of_urls(tmp_path: pathlib.Path) -> None:
        """Assert that passing an empty list to ``filter_urls`` returns an empty list."""
        # No arrange
        # Act
        result = filter_urls([], tmp_path)

        # Assert
        assert result == []


class TestDownloadOneZillowListing:
    @staticmethod
    def test_simple(tmp_path: pathlib.Path, mocker) -> None:
        """
        Test the happy path where ``download_one_zillow_listing`` downloads the expected
        index.html file.
        """

        # Arrange
        def create_empty_file(path: pathlib.Path) -> None:
            path.parent.mkdir(parents=True)
            path.touch()

        downloaded_file = tmp_path.joinpath(
            "https_www.zillow.com",
            "www.zillow.com",
            "homedetails",
            "123-Fake-St-Emerald-City-MO-12345",
            "87654321_zpid",
            "index.html",
        )

        mock_download_webpage = mocker.patch(
            "download_zillow_listings.main.download_webpage",
            side_effect=lambda *args, **kwargs: create_empty_file(downloaded_file),
        )
        zillow_url_to_download = "https://www.zillow.com/homedetails/123-Fake-St-Emerald-City-MO-12345/87654321_zpid/"

        # Act
        result = download_one_zillow_listing(
            ZillowUrl(zillow_url_to_download),
            tmp_path,
        )

        # Assert
        assert result == downloaded_file
        mock_download_webpage.assert_called_once_with(
            zillow_url_to_download, download_folder=tmp_path, open_in_browser=False
        )

    @staticmethod
    def test_download_fails(tmp_path: pathlib.Path, mocker) -> None:
        """
        Assert that the expected error is raised when ``download_one_zillow_listing`` fails to download
        the Zillow listing.
        """
        # Arrange

        expected_downloaded_file = tmp_path.joinpath(
            "https_www.zillow.com",
            "www.zillow.com",
            "homedetails",
            "123-Fake-St-Emerald-City-MO-12345",
            "87654321_zpid",
            "index.html",
        )

        mock_download_webpage = mocker.patch(
            "download_zillow_listings.main.download_webpage"
        )
        zillow_url_to_download = "https://www.zillow.com/homedetails/123-Fake-St-Emerald-City-MO-12345/87654321_zpid/"

        # Act and assert
        with pytest.raises(MissingIndexHtml) as exc:
            download_one_zillow_listing(ZillowUrl(zillow_url_to_download), tmp_path)

        mock_download_webpage.assert_called_once_with(
            zillow_url_to_download, download_folder=tmp_path, open_in_browser=False
        )

        exc.value: MissingIndexHtml
        assert exc.value.expected_index_html == expected_downloaded_file
        assert exc.value.url == ZillowUrl(zillow_url_to_download)


class TestDownloadMultipleZillowListings:
    @classmethod
    @pytest.fixture(scope="function", name="empty_dir")
    def fixture_empty_dir(cls, tmp_path: pathlib.Path) -> pathlib.Path:
        """
        Return a temporary directory and delete its contents after the test exits.

        Use this to replace ``tempfile.TemporaryDirectory``, which creates an empty
        directory. The advantage of this fixture is its path is deterministic.
        """
        yield tmp_path
        shutil.rmtree(tmp_path, ignore_errors=False)

    @staticmethod
    def test_download_one_listing(mocker, empty_dir: pathlib.Path) -> None:
        """
        Given a list of one Zillow listing, assert that the expected index.html
        file is downloaded.
        """

        # Arrange
        tmp_download_dir = empty_dir.joinpath("tmp_download_dir")
        dst_dir_for_index_html = empty_dir.joinpath("dst")

        def _mock_TemporaryDirectory_enter() -> str:
            tmp_download_dir.mkdir(parents=True)
            return str(tmp_download_dir)

        # Mock the ``tempfile.TemporaryDirectory`` context manager
        mock_temporary_directory = mocker.patch(
            "download_zillow_listings.main.tempfile.TemporaryDirectory"
        )
        mock_temporary_directory.return_value.__enter__ = mocker.MagicMock(
            side_effect=_mock_TemporaryDirectory_enter
        )

        def _mock_download_one_zillow_listing(url, download_dir) -> pathlib.Path:
            fake_downloaded_listing = download_dir.joinpath("index.html")
            # ``tmp_download_dir`` should already be created.
            fake_downloaded_listing.touch()
            return fake_downloaded_listing

        mock_download_one_zillow_listing = mocker.patch(
            "download_zillow_listings.main.download_one_zillow_listing",
            side_effect=_mock_download_one_zillow_listing,
        )

        url_to_download = ZillowUrl(
            "https://www.zillow.com/homedetails/123-Fake-St-Emerald-City-MO-12345/87654321_zpid/"
        )

        # Act
        download_multiple_zillow_listings(
            [url_to_download],
            download_dir_root=dst_dir_for_index_html,
            interval_between_downloads=0,
        )

        # Assert
        mock_download_one_zillow_listing.assert_called_once_with(
            url_to_download, tmp_download_dir
        )
        assert dst_dir_for_index_html.joinpath(
            "123-Fake-St-Emerald-City-MO-12345", "index.html"
        ).exists()

    @staticmethod
    def test_multiple_listings(mocker, empty_dir: pathlib.Path) -> None:
        """
        Given multiple listings to download, assert that they are in fact downloaded.
        """

        # Arrange
        tmp_download_dir = empty_dir.joinpath("tmp_download_dir")
        tmp_dir_counter = itertools.count()

        def _mock_TemporaryDirectory_enter() -> str:
            _tmp_download_dir = tmp_download_dir.joinpath(str(next(tmp_dir_counter)))
            _tmp_download_dir.mkdir(parents=True)
            return str(_tmp_download_dir)

        # Mock the ``tempfile.TemporaryDirectory`` context manager
        mock_temporary_directory = mocker.patch(
            "download_zillow_listings.main.tempfile.TemporaryDirectory"
        )
        mock_temporary_directory.return_value.__enter__ = mocker.MagicMock(
            side_effect=_mock_TemporaryDirectory_enter
        )

        def _mock_download_one_zillow_listing(url, download_dir) -> pathlib.Path:
            fake_downloaded_listing = download_dir.joinpath("index.html")
            # ``tmp_download_dir`` should already be created.
            fake_downloaded_listing.touch()
            return fake_downloaded_listing

        mock_download_one_zillow_listing = mocker.patch(
            "download_zillow_listings.main.download_one_zillow_listing",
            side_effect=_mock_download_one_zillow_listing,
        )

        urls_to_download = [
            ZillowUrl(
                "https://www.zillow.com/homedetails/123-Fake-St-Emerald-City-MO-12345/87654321_zpid/"
            ),
            ZillowUrl(
                "https://www.zillow.com/homedetails/LOT-Fake-St-Emerald-City-MO-12345/87654321_zpid/"
            ),
        ]
        dst_dir_for_index_html = empty_dir.joinpath("dst")

        # Act
        download_multiple_zillow_listings(
            urls_to_download,
            download_dir_root=dst_dir_for_index_html,
            interval_between_downloads=0,
        )

        # Assert
        mock_download_one_zillow_listing.assert_has_calls(
            [
                mocker.call(urls_to_download[0], tmp_download_dir.joinpath("0")),
                mocker.call(urls_to_download[1], tmp_download_dir.joinpath("1")),
            ]
        )
        assert dst_dir_for_index_html.joinpath(
            "123-Fake-St-Emerald-City-MO-12345", "index.html"
        ).exists()
        assert dst_dir_for_index_html.joinpath(
            "LOT-Fake-St-Emerald-City-MO-12345", "index.html"
        ).exists()
