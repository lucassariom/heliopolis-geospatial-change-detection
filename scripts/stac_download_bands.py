#!/usr/bin/env python3
"""
Download selected Sentinel-2 L2A assets from the Copernicus Data Space S3 bucket.

The script:
1. Fetches a STAC Item by ID.
2. Reads the requested asset hrefs.
3. Parses s3://eodata/<key>.
4. Downloads only those assets with boto3.
5. Prints basic raster metadata after download.

Credentials are read from:
- CDSE_S3_ACCESS_KEY
- CDSE_S3_SECRET_KEY
"""

import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

import boto3
import requests
import rasterio

STAC_BASE = "https://stac.dataspace.copernicus.eu/v1"
COLLECTION = "sentinel-2-l2a"
S3_ENDPOINT = "https://eodata.dataspace.copernicus.eu"


def parse_s3_href(href: str):
    parsed = urlparse(href)
    if parsed.scheme != "s3":
        raise ValueError(f"Expected s3:// href, got: {href}")
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    return bucket, key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--item-id", required=True)
    parser.add_argument(
        "--assets",
        nargs="+",
        default=["B04_10m", "B08_10m"],
        help="STAC asset keys to download",
    )
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    access_key = os.getenv("CDSE_S3_ACCESS_KEY")
    secret_key = os.getenv("CDSE_S3_SECRET_KEY")

    if not access_key or not secret_key:
        raise RuntimeError(
            "CDSE_S3_ACCESS_KEY and CDSE_S3_SECRET_KEY must be set "
            "in the current shell."
        )

    item_url = f"{STAC_BASE}/collections/{COLLECTION}/items/{args.item_id}"
    print(f"Fetching STAC Item:\n{item_url}\n")

    response = requests.get(item_url, timeout=60)
    response.raise_for_status()
    item = response.json()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="default",
    )

    print(f"Item: {item.get('id')}")
    print(f"Datetime: {item.get('properties', {}).get('datetime')}")
    print()

    for asset_key in args.assets:
        asset = item.get("assets", {}).get(asset_key)
        if asset is None:
            print(f"{asset_key}: NOT FOUND")
            continue

        href = asset.get("href")
        bucket, key = parse_s3_href(href)

        filename = Path(key).name
        local_path = out_dir / filename

        print(f"Downloading {asset_key}")
        print(f"  S3:    {href}")
        print(f"  Local: {local_path}")

        s3.download_file(bucket, key, str(local_path))

        size_mb = local_path.stat().st_size / (1024 * 1024)
        print(f"  Size:  {size_mb:.2f} MB")

        try:
            with rasterio.open(local_path) as src:
                print(f"  CRS:   {src.crs}")
                print(f"  Size:  {src.width} x {src.height} pixels")
                print(f"  Pixel: {src.res[0]:.2f} x {src.res[1]:.2f} m")
                print(f"  Dtype: {src.dtypes[0]}")
        except Exception as exc:
            print(f"  Raster metadata could not be read: {exc}")

        print()

    print("Download finished.")


if __name__ == "__main__":
    main()
