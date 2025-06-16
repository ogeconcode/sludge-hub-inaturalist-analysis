# Sludge Hub iNaturalist Mapping & Analysis

## Overview
This repository hosts the code and generated maps for spatial analysis of iNaturalist observations related to The Sludge Hub projects in Mineral County, West Virginia. It provides interactive visualizations of biodiversity, with a particular focus on **pollinator conservation**, offering granularity beyond iNaturalist's built-in project settings. The live maps are accessible via GitHub Pages, providing a clearer spatial understanding of biodiversity in relation to our project sites.

## Features
* **Interactive Maps:** Visualizations of observations around the main Sludge Hub collaborator property site and the apiary, including various concentric buffer zones.
* **Regular Data Updates:** Automated pulls from the iNaturalist API ensure the maps reflect the latest research-grade observations. Stay tuned for more updates and new features!
* **Detailed Spatial Analysis:** Provides insights into species distribution and ecological context within and around the project areas in Mineral County, WV.

## Explore the Maps
* [View the Live iNaturalist Maps](https://ogeconcode.github.io/sludge-hub-inaturalist-analysis/docs/)
* [Sludge Hub Official iNaturalist Project Page](https://www.inaturalist.org/projects/the-sludge-hub)

## Support & Collaboration
This project and its data collection processes are proudly supported by:
* [The Sludge Hub & Company](https://www.sludgehub.org/)
* [West Virginia Beekeeping Association](https://www.wvbeekeepers.org/)
* [GROW Externships](https://www.growexternships.org/)

## Data Source & Methodology
All observation data is sourced directly from the [iNaturalist API](https://api.inaturalist.org/v1/docs/). Data filtering includes "Research Grade" observations. Buffer zones are calculated using standard geospatial libraries (e.g., Shapely, GeoPandas) around key Sludge Hub research areas. For more detailed information on the scripts and data processing methodology, please refer to the project code within this repository.

## Reusability
The project code is designed with reusability in mind. It can be adapted and re-purposed by other users for their site-specific iNaturalist project codes and geospatial boundaries, making it a valuable tool for similar ecological monitoring initiatives.

## Contact
For questions about the data or maps, please consider [opening an issue on this GitHub repository](https://github.com/ogeconcode/sludge-hub-inaturalist-analysis/issues). For direct inquiries, you may contact Olivia Gonzalez via [LinkedIn](https://www.linkedin.com/in/olivia-j-gonzalez/).

---

## Disclaimer
*This page (and the associated live maps) are an independent publication and do not necessarily reflect the official views or positions of The Sludge Hub & Company or other project collaborators.*
