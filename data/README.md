# Data

Large source imagery is intentionally not included in this repository.

Local working data used in the case study included:

- AOI GeoJSON
- original Sentinel-2 L2A B04_10m JP2
- original Sentinel-2 L2A B08_10m JP2
- derived BOA reflectance GeoTIFFs
- derived NDVI GeoTIFFs
- Delta NDVI GeoTIFF
- classified change GeoTIFF
- CSV summaries

The original imagery can be re-discovered through STAC and retrieved from Copernicus Data Space Ecosystem object storage using the scripts in `scripts/`.

Never commit S3 credentials.
