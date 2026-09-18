# Methodology

## Data selection

Sentinel-2 Level-2A imagery was searched through the Copernicus Data Space STAC catalogue using the study-area geometry, September date windows and a scene-level cloud-cover filter. The final comparison used observations from 2021-09-22 and 2026-09-16 in the same MGRS tile.

## Asset retrieval

The STAC Items were inspected for 10 m B04 (Red) and B08 (Near Infrared) assets. Original JP2 objects were retrieved from Copernicus object storage using S3 credentials loaded from environment variables. Credentials are never stored in code or committed to Git.

## Radiometric conversion

Product metadata was parsed for `BOA_QUANTIFICATION_VALUE` and band-specific `BOA_ADD_OFFSET`. For both selected products the relevant parameters were:

```text
BOA_QUANTIFICATION_VALUE = 10000
B04 BOA_ADD_OFFSET = -1000
B08 BOA_ADD_OFFSET = -1000
```

Stored digital numbers were converted to bottom-of-atmosphere reflectance before index calculation:

```text
reflectance = (DN + BOA_ADD_OFFSET) / BOA_QUANTIFICATION_VALUE
```

## NDVI

NDVI was calculated from B08 and B04:

```text
NDVI = (B08 - B04) / (B08 + B04)
```

The AOI was reprojected to the raster CRS and used to crop each scene. Invalid pixels and NoData were excluded.

## Native-grid temporal comparison

Before subtraction, the two derived NDVI rasters were checked for identical CRS, dimensions, pixel size and affine transform. All checks passed, allowing direct pixel-to-pixel comparison without resampling.

```text
Delta NDVI = NDVI_2026 - NDVI_2021
```

For descriptive summarization, an operational threshold of ±0.05 was used:

- Delta NDVI < -0.05: decrease
- -0.05 <= Delta NDVI <= +0.05: relatively stable
- Delta NDVI > +0.05: increase

This threshold is a case-study convention rather than a universal ecological threshold.

## Interpretation limits

The analysis identifies spectral change between two observations. It does not establish ecological causality. Potential confounders include rainfall, phenology, land-management changes, residual atmospheric effects, cloud/shadow contamination and the limited temporal sampling of two dates.
