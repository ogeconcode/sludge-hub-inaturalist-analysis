# Sludge Hub Biodiversity Mapping

## Overview

This repository provides spatial analysis and interactive mapping of iNaturalist observations across five West Virginia ecological regions. It supports The Sludge Hub's ecological monitoring work by visualizing biodiversity patterns relevant to mine land restoration and pollinator conservation.

The project combines observations from the [Sludge Hub iNaturalist project](https://www.inaturalist.org/projects/the-sludge-hub) with broader community observations to enable regional comparison across the state.

**[View the Live Maps](https://ogeconcode.github.io/sludge-hub-inaturalist-analysis/)**

## Study Regions

The analysis covers five multi-county regions across West Virginia:

- **Potomac Highlands** — Mineral, Grant, and Hampshire counties
- **Monongahela Valley** — Monongalia, Preston, and Marion counties
- **Kanawha Valley** — Kanawha, Putnam, and Fayette counties
- **Greenbrier / New River** — Greenbrier, Monroe, and Summers counties
- **Eastern Panhandle** — Jefferson, Berkeley, and Morgan counties

Each region is defined by a geographic bounding box. Maps display observations with buffer zones around regional reference points, providing spatial context for biodiversity distribution.

## Features

- **Multi-region comparison** across diverse West Virginia landscapes
- **Pollinator highlighting** — insect observations are visually distinguished to support pollinator conservation focus
- **Two data sources** — Sludge Hub project observations and broader iNaturalist community observations
- **Interactive Folium maps** with taxonomic color coding and layer controls
- **Reusable codebase** — adaptable for other iNaturalist projects and geographic areas

## Repository Structure

```
├── .github/workflows/   GitHub Actions for Pages deployment
├── data/                Generated data files (gitignored)
├── docs/                GitHub Pages content
│   ├── index.html       Landing page
│   ├── last_updated.txt Timestamp from last data pull
│   └── maps/            Generated interactive maps
├── src/
│   ├── config.py        Local configuration (gitignored)
│   ├── config_template.py   Template for config.py
│   ├── inat_data_pull.py    API data retrieval
│   └── spatial_analysis.py  Spatial analysis and map generation
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

## Setup and Usage

### 1. Clone and configure

```bash
git clone https://github.com/ogeconcode/sludge-hub-inaturalist-analysis.git
cd sludge-hub-inaturalist-analysis
pip install -r requirements.txt
```

Copy the configuration template and fill in your values:

```bash
cp src/config_template.py src/config.py
```

Edit `src/config.py` with your iNaturalist project ID and study region definitions. See `config_template.py` for documentation on each setting.

### 2. Pull data

```bash
python -m src.inat_data_pull
```

This queries the iNaturalist API for your project observations and each study region, then saves a combined dataset to `data/observations_cleaned.csv`.

### 3. Run analysis and generate maps

```bash
python -m src.spatial_analysis
```

This assigns observations to study regions, generates interactive maps in `docs/maps/`, and saves the analyzed dataset.

### 4. Deploy

Commit the updated files in `docs/` and push to `main`. GitHub Actions will deploy to GitHub Pages automatically.

## Data and Methodology

Observation data is sourced from the [iNaturalist API](https://api.inaturalist.org/v1/docs/). The dataset includes research-grade and needs-identification observations (casual-grade excluded). Buffer zones are calculated using Shapely and GeoPandas around regional reference points. Maps are rendered with Folium.

## Support and Collaboration

This project is supported by [The Sludge Hub & Company](https://www.sludgehub.org/), the [West Virginia Beekeeping Association](https://www.wvbeekeepers.org/), and [GROW Externships](https://www.growexternships.org/).

## Contact

For questions, [open an issue](https://github.com/ogeconcode/sludge-hub-inaturalist-analysis/issues) or contact Olivia Gonzalez via [LinkedIn](https://www.linkedin.com/in/olivia-j-gonzalez/).

## License

[MIT](LICENSE)

---

*This project is an independent publication and does not necessarily reflect the official views of The Sludge Hub & Company or other collaborators.*
