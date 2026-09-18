#!/usr/bin/env python3
"""
Compute an AOI-clipped Sentinel-2 L2A NDVI from original B04/B08 JP2 assets.

The product metadata is read through CDSE S3 so that BOA quantification and
band-specific additive offsets are applied before NDVI calculation.
"""

import argparse
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import boto3
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
from botocore.config import Config
from rasterio.mask import mask

STAC_BASE = "https://stac.dataspace.copernicus.eu/v1"
COLLECTION = "sentinel-2-l2a"
S3_ENDPOINT = "https://eodata.dataspace.copernicus.eu"
OUTPUT_NODATA = -9999.0
BAND_ID_BY_NAME = {"B04": "3", "B08": "7"}


def parse_s3_href(href):
    p = urlparse(href)
    if p.scheme != "s3":
        raise ValueError(f"Expected s3:// href, got {href}")
    return p.netloc, p.path.lstrip("/")


def s3_client():
    access_key = os.getenv("CDSE_S3_ACCESS_KEY")
    secret_key = os.getenv("CDSE_S3_SECRET_KEY")
    if not access_key or not secret_key:
        raise RuntimeError("CDSE S3 environment variables are not loaded.")
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="default",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def fetch_item(item_id):
    url = f"{STAC_BASE}/collections/{COLLECTION}/items/{item_id}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_product_metadata(item, s3):
    href = item["assets"]["product_metadata"]["href"]
    bucket, key = parse_s3_href(href)
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def local_tag(tag):
    return tag.split("}", 1)[-1]


def parse_radiometry(xml_bytes):
    root = ET.fromstring(xml_bytes)
    quant = None
    offsets = {}
    for elem in root.iter():
        name = local_tag(elem.tag)
        text = (elem.text or "").strip()
        if name == "BOA_QUANTIFICATION_VALUE" and text:
            quant = float(text)
        elif name == "BOA_ADD_OFFSET" and text:
            offsets[str(elem.attrib["band_id"])] = float(text)
    if quant is None or not offsets:
        raise RuntimeError("Could not parse BOA radiometric metadata.")
    return quant, offsets


def crop_to_aoi(path, aoi_path):
    with rasterio.open(path) as src:
        aoi = gpd.read_file(aoi_path).to_crs(src.crs)
        shapes = [g.__geo_interface__ for g in aoi.geometry if g is not None]
        data, transform = mask(src, shapes, crop=True, filled=False, all_touched=False)
        arr = data[0].astype("float32")
        invalid = np.ma.getmaskarray(arr) | (np.asarray(arr) == 0)
        arr = np.asarray(arr, dtype="float32")
        arr[invalid] = np.nan
        profile = src.profile.copy()
        profile.update(height=arr.shape[0], width=arr.shape[1], transform=transform)
        return arr, profile


def write_float(path, arr, profile):
    p = profile.copy()
    p.update(driver="GTiff", dtype="float32", count=1,
             nodata=OUTPUT_NODATA, compress="deflate")
    out = np.where(np.isfinite(arr), arr, OUTPUT_NODATA).astype("float32")
    with rasterio.open(path, "w", **p) as dst:
        dst.write(out, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--item-id", required=True)
    ap.add_argument("--b04", required=True)
    ap.add_argument("--b08", required=True)
    ap.add_argument("--aoi", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", default=None,
                    help="Output label, e.g. 2021 or 2026. Defaults to acquisition year.")
    args = ap.parse_args()

    item = fetch_item(args.item_id)
    datetime_text = item.get("properties", {}).get("datetime", "")
    label = args.label or datetime_text[:4] or "scene"

    s3 = s3_client()
    quant, offsets = parse_radiometry(fetch_product_metadata(item, s3))
    red_offset = offsets[BAND_ID_BY_NAME["B04"]]
    nir_offset = offsets[BAND_ID_BY_NAME["B08"]]

    red_dn, profile = crop_to_aoi(args.b04, args.aoi)
    nir_dn, nir_profile = crop_to_aoi(args.b08, args.aoi)

    if red_dn.shape != nir_dn.shape or profile["transform"] != nir_profile["transform"]:
        raise RuntimeError("B04 and B08 crops do not share the same grid.")

    red = (red_dn + red_offset) / quant
    nir = (nir_dn + nir_offset) / quant

    denominator = nir + red
    valid = np.isfinite(red) & np.isfinite(nir) & (np.abs(denominator) > 1e-12)

    ndvi = np.full(red.shape, np.nan, dtype="float32")
    ndvi[valid] = (nir[valid] - red[valid]) / denominator[valid]
    ndvi[(ndvi < -1) | (ndvi > 1)] = np.nan

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    red_out = out_dir / f"b04_reflectance_{label}_aoi.tif"
    nir_out = out_dir / f"b08_reflectance_{label}_aoi.tif"
    ndvi_out = out_dir / f"ndvi_{label}_from_stac_s3.tif"
    csv_out = out_dir / f"ndvi_{label}_from_stac_s3_summary.csv"

    write_float(red_out, red, profile)
    write_float(nir_out, nir, profile)
    write_float(ndvi_out, ndvi, profile)

    pixel_area = abs(profile["transform"].a * profile["transform"].e -
                     profile["transform"].b * profile["transform"].d)
    count = int(np.isfinite(ndvi).sum())

    summary = {
        "item_id": item.get("id"),
        "datetime": datetime_text,
        "boa_quantification_value": quant,
        "b04_add_offset": red_offset,
        "b08_add_offset": nir_offset,
        "valid_pixel_count": count,
        "pixel_area_m2": pixel_area,
        "valid_area_m2": count * pixel_area,
        "valid_area_ha": count * pixel_area / 10000.0,
        "ndvi_min": float(np.nanmin(ndvi)),
        "ndvi_max": float(np.nanmax(ndvi)),
        "ndvi_mean": float(np.nanmean(ndvi)),
        "ndvi_stddev": float(np.nanstd(ndvi)),
    }
    pd.DataFrame([summary]).to_csv(csv_out, index=False)

    print(f"Label: {label}")
    for k, v in summary.items():
        print(f"{k}: {v:.6f}" if isinstance(v, float) else f"{k}: {v}")
    print(f"NDVI: {ndvi_out}")
    print(f"Summary: {csv_out}")


if __name__ == "__main__":
    main()
