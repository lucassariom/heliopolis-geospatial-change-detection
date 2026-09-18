#!/usr/bin/env python3
"""
Diagnose CDSE S3 access for one exact Sentinel-2 asset.

Tests both official CDSE S3 endpoints with:
- path-style addressing
- S3 Signature V4
- ranged GET of 1 byte (avoids boto3 download_file's HEAD preflight)

No credentials are printed.
"""

import os
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

ASSET_HREF = (
    "s3://eodata/Sentinel-2/MSI/L2A/2026/09/16/"
    "S2B_MSIL2A_20260916T134209_N0512_R124_T22JBR_20260916T184504.SAFE/"
    "GRANULE/L2A_T22JBR_A049771_20260916T134819/IMG_DATA/R10m/"
    "T22JBR_20260916T134209_B04_10m.jp2"
)

ENDPOINTS = [
    "https://eodata.dataspace.copernicus.eu",
    "https://eodata.ams.dataspace.copernicus.eu",
]


def parse_s3(uri):
    p = urlparse(uri)
    return p.netloc, p.path.lstrip("/")


def make_client(endpoint, access_key, secret_key):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="default",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


def show_error(prefix, exc):
    err = exc.response.get("Error", {})
    print(f"{prefix}: FAILED")
    print(f"  Code:    {err.get('Code')}")
    print(f"  Message: {err.get('Message')}")


def main():
    access_key = os.getenv("CDSE_S3_ACCESS_KEY")
    secret_key = os.getenv("CDSE_S3_SECRET_KEY")

    if not access_key or not secret_key:
        raise RuntimeError("CDSE S3 environment variables are not loaded.")

    bucket, key = parse_s3(ASSET_HREF)

    print("Credentials present: True")
    print(f"Bucket: {bucket}")
    print(f"Key: {key}\n")

    any_get_ok = False

    for endpoint in ENDPOINTS:
        print("=" * 72)
        print(f"Endpoint: {endpoint}")
        client = make_client(endpoint, access_key, secret_key)

        try:
            resp = client.head_object(Bucket=bucket, Key=key)
            print("HEAD: OK")
            print(f"  ContentLength: {resp.get('ContentLength')}")
        except ClientError as exc:
            show_error("HEAD", exc)

        try:
            resp = client.get_object(Bucket=bucket, Key=key, Range="bytes=0-0")
            data = resp["Body"].read()
            print("RANGED GET: OK")
            print(f"  Bytes returned: {len(data)}")
            any_get_ok = True
        except ClientError as exc:
            show_error("RANGED GET", exc)

        print()

    if any_get_ok:
        print("RESULT: At least one endpoint can read the object.")
        print("We can download with get_object() instead of download_file().")
    else:
        print("RESULT: Both endpoints rejected the ranged GET.")
        print("This points to credentials/permissions/propagation rather than HEAD only.")


if __name__ == "__main__":
    main()
