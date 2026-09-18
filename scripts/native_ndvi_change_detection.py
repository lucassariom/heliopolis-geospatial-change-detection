#!/usr/bin/env python3
"""
Native-grid NDVI change detection for Heliópolis.

This script expects two NDVI rasters derived from the native Sentinel-2 10 m grid.
It deliberately does NOT resample. Instead, it first verifies that both rasters
have the same CRS, dimensions and affine transform. If they match, it computes:

    Delta NDVI = NDVI_2026 - NDVI_2021

and classifies change using the operational threshold +/- 0.05:

    -1 = decrease
     0 = relatively stable
     1 = increase

The +/- 0.05 threshold is a case-study convention, not a universal ecological
threshold.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

OUTPUT_NODATA = -9999.0
THRESHOLD = 0.05


def read_ndvi(path):
    with rasterio.open(path) as src:
        arr = src.read(1, masked=True).filled(np.nan).astype("float32")
        return {
            "array": arr,
            "profile": src.profile.copy(),
            "crs": src.crs,
            "transform": src.transform,
            "width": src.width,
            "height": src.height,
            "res": src.res,
        }


def same_transform(a, b, atol=1e-9):
    return np.allclose(tuple(a), tuple(b), atol=atol, rtol=0)


def valid_ndvi(arr):
    return np.isfinite(arr) & (arr >= -1.0) & (arr <= 1.0)


def write_float_raster(path, array, profile):
    out_profile = profile.copy()
    out_profile.update(
        driver="GTiff",
        dtype="float32",
        count=1,
        nodata=OUTPUT_NODATA,
        compress="deflate",
    )
    out = np.where(np.isfinite(array), array, OUTPUT_NODATA).astype("float32")
    with rasterio.open(path, "w", **out_profile) as dst:
        dst.write(out, 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ndvi-2021", required=True)
    parser.add_argument("--ndvi-2026", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    r21 = read_ndvi(args.ndvi_2021)
    r26 = read_ndvi(args.ndvi_2026)

    print("=== Grid validation ===")
    print(f"2021 CRS:       {r21['crs']}")
    print(f"2026 CRS:       {r26['crs']}")
    print(f"2021 dimensions:{r21['width']} x {r21['height']}")
    print(f"2026 dimensions:{r26['width']} x {r26['height']}")
    print(f"2021 pixel size:{r21['res']}")
    print(f"2026 pixel size:{r26['res']}")

    checks = {
        "same_crs": r21["crs"] == r26["crs"],
        "same_dimensions": (
            r21["width"] == r26["width"] and r21["height"] == r26["height"]
        ),
        "same_transform": same_transform(r21["transform"], r26["transform"]),
    }

    for key, value in checks.items():
        print(f"{key}: {value}")

    if not all(checks.values()):
        raise RuntimeError(
            "The two NDVI rasters are not on the exact same grid. "
            "Do not compare pixel-by-pixel without alignment."
        )

    ndvi21 = r21["array"]
    ndvi26 = r26["array"]

    valid = valid_ndvi(ndvi21) & valid_ndvi(ndvi26)

    delta = np.full(ndvi21.shape, np.nan, dtype="float32")
    delta[valid] = ndvi26[valid] - ndvi21[valid]

    classes = np.full(ndvi21.shape, np.nan, dtype="float32")
    classes[valid & (delta < -THRESHOLD)] = -1
    classes[valid & (delta >= -THRESHOLD) & (delta <= THRESHOLD)] = 0
    classes[valid & (delta > THRESHOLD)] = 1

    pixel_area_m2 = abs(
        r21["transform"].a * r21["transform"].e
        - r21["transform"].b * r21["transform"].d
    )
    valid_count = int(valid.sum())

    summary = {
        "valid_pixel_count": valid_count,
        "pixel_area_m2": pixel_area_m2,
        "valid_area_m2": valid_count * pixel_area_m2,
        "valid_area_ha": valid_count * pixel_area_m2 / 10000.0,
        "ndvi_2021_mean_valid_overlap": float(np.nanmean(ndvi21[valid])),
        "ndvi_2026_mean_valid_overlap": float(np.nanmean(ndvi26[valid])),
        "delta_min": float(np.nanmin(delta)),
        "delta_max": float(np.nanmax(delta)),
        "delta_mean": float(np.nanmean(delta)),
        "delta_stddev": float(np.nanstd(delta)),
    }

    rows = []
    labels = {-1: "decrease", 0: "stable", 1: "increase"}
    for value in (-1, 0, 1):
        count = int(np.sum(classes == value))
        area_m2 = count * pixel_area_m2
        rows.append(
            {
                "class_value": value,
                "class_name": labels[value],
                "pixel_count": count,
                "area_m2": area_m2,
                "area_ha": area_m2 / 10000.0,
                "pct_of_valid_overlap": (
                    count / valid_count * 100.0 if valid_count else np.nan
                ),
            }
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    delta_path = out_dir / "delta_ndvi_2021_2026_native10m.tif"
    class_path = out_dir / "delta_ndvi_classes_2021_2026_native10m.tif"
    summary_path = out_dir / "native10m_change_summary.csv"
    classes_path = out_dir / "native10m_change_classes.csv"

    write_float_raster(delta_path, delta, r21["profile"])
    write_float_raster(class_path, classes, r21["profile"])
    pd.DataFrame([summary]).to_csv(summary_path, index=False)
    pd.DataFrame(rows).to_csv(classes_path, index=False)

    print("\n=== Native 10 m change detection ===")
    for key, value in summary.items():
        if isinstance(value, float):
            print(f"{key}: {value:.6f}")
        else:
            print(f"{key}: {value}")

    print("\n=== Change classes (threshold +/- 0.05) ===")
    print(pd.DataFrame(rows).to_string(index=False))

    print("\nOutputs:")
    print(f"  {delta_path}")
    print(f"  {class_path}")
    print(f"  {summary_path}")
    print(f"  {classes_path}")


if __name__ == "__main__":
    main()
