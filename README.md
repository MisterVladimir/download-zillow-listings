# Welcome to `download-zillow-listings`

Download real estate listings off Zillow before they fly off the market.

## Quickstart

- Install the Python virtual environment. See `poetry` docs [here](https://python-poetry.org/docs/basic-usage/).

  ```shell
  poetry install
  ```

- Update the `_urls_to_download` variable in `download_zillow_listings/main.py` with the listings you want to download.
  A listing's URL typically looks like https://www.zillow.com/homedetails/123-Fake-St-Emerald-City-MO-12345/87654321_zpid/.
- Run the `main.py` script.

  ```shell
  poetry shell
  python -m download_zillow_listings.main
  ```

- Listings will be downloaded to the `downloaded-webpages` subdirectory of this repo.
  Each listing webpage is saved an `index.html` file located in a folder whose name matches the listing street address.
