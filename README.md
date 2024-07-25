# GEONH3

GeoNH3 calculates the locational cost of green ammonia production, storage, transport, and conversion to meet demand in a specified location. 
These costs can be compared to current or projected prices for energy and chemical feedstocks in the region to assess the competitiveness of green ammonia.
The model outputs the levelized cost of ammonia (LCOA) at the demand location including production, storage, transport, and conversion costs. 

GeoNH3 is a modified version of the [GeoH2](https://github.com/ClimateCompatibleGrowth/GeoH2) model. 
Whereas GeoH2 models the production of green hydrogen with electrolysis, GeoNH3 models the production of green ammonia using the Haber-Bosch process.

This repo can be used in a similar way to GeoH2. 
As such, please refer to the [GeoH2 ReadMe](https://github.com/ClimateCompatibleGrowth/GeoH2/blob/main/README.md) for usage instructions, limitations, and guidance for citation. 
When referring to these instructions, please note the following differences in naming:
 - Where `optimize_transport_and_conversion.py` is run in GeoH2, `optimize_transport.py` is run here.
 - Where `optimize_hydrogen_plant.py` is run in GeoH2, `optimize_ammonia_plant.py` is run here.
 - Where `total_hydrogen_cost.py` is run in GeoH2, `total_ammonia_cost.py` is run here.
 - Whereas `environment.yaml` creates an environment named `geoh2` in GeoH2, it creates an environment called `geonh3` in GeoNH3.

