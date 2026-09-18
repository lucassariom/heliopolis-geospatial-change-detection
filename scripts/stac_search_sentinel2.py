#!/usr/bin/env python3
"""
Search Sentinel-2 L2A scenes in the Copernicus Data Space STAC catalog.
"""

import argparse
import json
from pathlib import Path

import pandas as pd
from pystac_client import Client

STAC_URL = "https://stac.dataspace.copernicus.eu/v1"
COLLECTION = "sentinel-2-l2a"


def load_geometry(path):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)

    obj_type = obj.get("type")

    if obj_type in {"Polygon", "MultiPolygon"}:
        return obj
    if obj_type == "Feature":
        return obj["geometry"]
    if obj_type == "FeatureCollection":
        features = obj.get("features", [])
        if not features:
            raise ValueError("The GeoJSON FeatureCollection contains no features.")
        if len(features) > 1:
            print(f"Warning: AOI contains {len(features)} features; using the first.")
        return features[0]["geometry"]

    raise ValueError(f"Unsupported GeoJSON type: {obj_type}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aoi", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--max-cloud", type=float, default=20.0)
    parser.add_argument("--max-items", type=int, default=50)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    geometry = load_geometry(args.aoi)

    print(f"Connecting to STAC catalog: {STAC_URL}")
    catalog = Client.open(STAC_URL)
    catalog.add_conforms_to("ITEM_SEARCH")

    print(
        f"Searching {COLLECTION} from {args.start} to {args.end} "
        f"with scene cloud cover <= {args.max_cloud}% ..."
    )

    search = catalog.search(
        collections=[COLLECTION],
        datetime=f"{args.start}/{args.end}",
        intersects=geometry,
        query={"eo:cloud_cover": {"lte": args.max_cloud}},
        max_items=args.max_items,
    )

    items = list(search.items())

    rows = []
    for item in items:
        props = item.properties
        rows.append(
            {
                "id": item.id,
                "datetime": props.get("datetime"),
                "cloud_cover_pct": props.get("eo:cloud_cover"),
                "platform": props.get("platform"),
                "constellation": props.get("constellation"),
                "gsd_m": props.get("gsd"),
                "mgrs_tile": props.get("s2:mgrs_tile"),
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        print("\nNo scenes matched the search.")
        return

    if "cloud_cover_pct" in df.columns:
        df = df.sort_values(
            by=["cloud_cover_pct", "datetime"],
            ascending=[True, True],
            na_position="last",
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)

    print(f"\nFound {len(df)} matching scene(s).")
    print("\nTop results:")
    print(df[["datetime", "cloud_cover_pct", "id"]].head(10).to_string(index=False))
    print(f"\nCSV saved to: {out_path}")


if __name__ == "__main__":
    main()
