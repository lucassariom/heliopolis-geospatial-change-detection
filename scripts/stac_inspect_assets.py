#!/usr/bin/env python3
"""
Inspect the assets exposed by a Copernicus STAC Item.
"""

import argparse
import requests

BASE_URL = "https://stac.dataspace.copernicus.eu/v1"
COLLECTION = "sentinel-2-l2a"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--item-id", required=True)
    args = parser.parse_args()

    url = f"{BASE_URL}/collections/{COLLECTION}/items/{args.item_id}"
    print(f"Requesting STAC Item:\n{url}\n")

    response = requests.get(url, timeout=60)
    response.raise_for_status()
    item = response.json()

    print(f"ID: {item.get('id')}")
    props = item.get("properties", {})
    print(f"Datetime: {props.get('datetime')}")
    print(f"Cloud cover: {props.get('eo:cloud_cover')}%")
    print(f"Collection: {item.get('collection')}")

    assets = item.get("assets", {})
    print(f"\nAssets exposed by this item: {len(assets)}\n")

    for key in sorted(assets):
        asset = assets[key]
        print(f"{key}")
        print(f"  type:  {asset.get('type')}")
        print(f"  roles: {asset.get('roles')}")
        print(f"  href:  {asset.get('href')}")
        print()

    print("=== 10 m bands relevant to this case study ===")
    for key in ("B02_10m", "B03_10m", "B04_10m", "B08_10m"):
        asset = assets.get(key)
        if asset:
            print(f"{key}: {asset.get('href')}")
        else:
            print(f"{key}: NOT FOUND")

if __name__ == "__main__":
    main()
