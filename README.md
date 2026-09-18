# Heliópolis Geospatial Change Detection

End-to-end geospatial case study combining historical UAV photogrammetry with a reproducible Sentinel-2 remote-sensing workflow.

## Project summary

The study area is a rural property associated with the Comunidade Heliópolis project in southern Brazil.

The original 2021 work used UAV imagery and photogrammetry to support terrain and lot planning. The newer analysis revisits the same area with Sentinel-2 Level-2A imagery and a programmatic workflow built with Python, STAC, S3, Rasterio, GeoPandas, NumPy and Pandas.

The satellite workflow searches imagery by AOI/date/cloud cover, discovers spectral assets through STAC, retrieves original Sentinel-2 bands from object storage, applies Level-2A radiometric metadata, computes NDVI, validates raster grids and performs pixel-level temporal change detection.

## Portfolio overview

![Heliópolis NDVI change-detection portfolio](docs/portfolio_overview.png)

A one-page visual summary is also available as [PDF](docs/portfolio_overview.pdf).

## Final native-grid results

Two September Sentinel-2 L2A observations were compared:

- 2021-09-22
- 2026-09-16

Both NDVI rasters were generated from original 10 m Sentinel-2 B04 (Red) and B08 (NIR) assets.

Grid validation before comparison:

- CRS: EPSG:32722
- Native pixel size: 10 x 10 m
- Cropped dimensions: 30 x 35 pixels
- Same CRS: True
- Same dimensions: True
- Same affine transform: True
- Resampling required for final comparison: No

### NDVI and change metrics

| Metric | Result |
|---|---:|
| Mean NDVI - 2021 | 0.614838 |
| Mean NDVI - 2026 | 0.747175 |
| Mean Delta NDVI | +0.132336 |
| Minimum Delta NDVI | -0.393781 |
| Maximum Delta NDVI | +0.600111 |
| Valid pixels | 724 |
| Rasterized valid area | 7.24 ha |

Operational change classification used a +/- 0.05 NDVI threshold:

| Class | Rule | Pixels | Area | Share of valid area |
|---|---|---:|---:|---:|
| Decrease | Delta NDVI < -0.05 | 50 | 0.50 ha | 6.91% |
| Relatively stable | -0.05 <= Delta NDVI <= +0.05 | 175 | 1.75 ha | 24.17% |
| Increase | Delta NDVI > +0.05 | 499 | 4.99 ha | 68.92% |

The +/- 0.05 threshold is an analytical convention for this case study, not a universal ecological threshold.

## Workflow

```text
AOI GeoJSON
    |
    v
Copernicus STAC search
    |
    +--> spatial intersection
    +--> date window
    +--> scene cloud-cover filter
    |
    v
STAC Item selection
    |
    v
Asset discovery
(B04_10m, B08_10m)
    |
    v
Copernicus S3 retrieval
    |
    v
Product metadata
(BOA quantification + additive offsets)
    |
    v
AOI reprojection + raster crop
    |
    v
DN -> BOA reflectance
    |
    v
NDVI = (NIR - Red) / (NIR + Red)
    |
    v
Native-grid validation
    |
    v
Pixel-to-pixel Delta NDVI
    |
    v
Change classification + CSV/GeoTIFF outputs
```

## Radiometric handling

For the selected products, the metadata reported:

```text
BOA_QUANTIFICATION_VALUE = 10000
B04 BOA_ADD_OFFSET = -1000
B08 BOA_ADD_OFFSET = -1000
```

The scripts convert the stored digital numbers to bottom-of-atmosphere reflectance before calculating NDVI:

```text
reflectance = (DN + BOA_ADD_OFFSET) / BOA_QUANTIFICATION_VALUE
```

Then:

```text
NDVI = (B08 - B04) / (B08 + B04)
```

## Independent validation

The 2026 NDVI computed directly from the original 10 m JP2 assets produced a mean of:

```text
0.747175
```

An earlier QGIS workflow based on a Copernicus Browser export produced approximately:

```text
0.747618
```

The close agreement provided an independent check of the processing logic. The final portfolio metrics use the native 10 m products rather than the browser-exported rasters.

## Repository structure

```text
.
├── README.md
├── requirements.txt
├── .gitignore
├── scripts/
│   ├── stac_search_sentinel2.py
│   ├── stac_inspect_assets.py
│   ├── stac_download_bands.py
│   ├── compute_ndvi_from_stac_s3.py
│   ├── native_ndvi_change_detection.py
│   └── cdse_s3_diagnose.py
├── docs/
│   ├── METHODOLOGY.md
│   ├── portfolio_overview.png
│   └── portfolio_overview.pdf
├── results/
│   ├── native10m_change_summary.csv
│   └── native10m_change_classes.csv
└── data/
    └── README.md
```

Large imagery and credentials are intentionally excluded from the repository.

## Python environment

Recommended: Python 3.13+ with a virtual environment.

```powershell
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Example - search Sentinel-2 with STAC

```powershell
python .\scripts\stac_search_sentinel2.py `
  --aoi ".\data\aoi_heliopolis.geojson" `
  --start 2026-09-01 `
  --end 2026-09-30 `
  --max-cloud 20 `
  --output ".\outputs\stac_search_2026.csv"
```

The September 2026 search returned the selected scene:

```text
S2B_MSIL2A_20260916T134209_N0512_R124_T22JBR_20260916T184504
```

with scene-level cloud cover reported as 0.01%.

The September 2021 comparison used:

```text
S2B_MSIL2A_20210922T134029_N0500_R124_T22JBR_20230115T001705
```

## S3 credentials

Do not hard-code credentials or commit them to Git.

The scripts read:

```text
CDSE_S3_ACCESS_KEY
CDSE_S3_SECRET_KEY
```

from environment variables.

## Historical UAV context

The same property had previously been mapped with a DJI Mavic Mini in 2021.

The historical photogrammetry workflow included:

- systematic nadir UAV imagery
- geotagged RGB photographs
- ground-control information supplied by a professional surveyor
- Agisoft Metashape image alignment
- depth maps and dense point cloud
- 3D model
- elevation model
- orthomosaic
- contour-based terrain analysis
- AutoCAD site/lot planning

That historical work was UAV-based RGB remote sensing/photogrammetry. The Sentinel-2 work in this repository is the later multispectral satellite component.

## Interpretation and limitations

The result is a spectral change analysis between two observations. It does not by itself prove ecological improvement or establish causality.

Potential drivers and limitations include:

- rainfall differences
- phenology and seasonality
- land-management changes
- atmospheric residuals
- cloud/shadow effects
- Sentinel-2 spatial resolution
- the use of only two dates
- the operational +/- 0.05 classification threshold

A stronger environmental conclusion would require a longer time series and additional contextual variables.

## Skills demonstrated

- GIS and raster/vector concepts
- CRS and projected coordinate systems
- GeoJSON and GeoTIFF
- Sentinel-2 Level-2A
- multispectral imagery
- Red / NIR spectral analysis
- NDVI
- STAC catalog search
- cloud-cover filtering
- S3 object storage
- Python
- Rasterio
- GeoPandas
- NumPy
- Pandas
- metadata parsing
- radiometric conversion
- raster masking/cropping
- affine-grid validation
- temporal change detection
- NoData handling
- reproducible analytical outputs

## Documentation references

- Copernicus Data Space Ecosystem - STAC product catalogue:
  https://documentation.dataspace.copernicus.eu/APIs/STAC.html
- Copernicus Data Space Ecosystem - S3 access:
  https://documentation.dataspace.copernicus.eu/APIs/S3.html
- Planet - STAC support:
  https://docs.planet.com/develop/apis/data/stac/

## Portfolio statement

A concise description suitable for a portfolio:

> Built an end-to-end Sentinel-2 change-detection workflow for a rural property previously mapped by UAV photogrammetry. Queried imagery programmatically via STAC, retrieved native spectral assets through S3, applied Level-2A radiometric metadata, calculated 10 m NDVI for 2021 and 2026, validated exact raster-grid compatibility, and performed pixel-level temporal change detection in Python. Mean NDVI increased from 0.615 to 0.747; using a +/- 0.05 operational threshold, 68.9% of the valid rasterized area showed an NDVI increase, 24.2% remained relatively stable, and 6.9% showed a decrease.
