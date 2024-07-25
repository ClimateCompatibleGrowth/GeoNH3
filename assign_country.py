#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Apr  2 12:05:51 2023

@author: Claire Halloran, University of Oxford

Assigns interest rate to different hexagons for different technology categories
based on their country.

Edited on Thu Jul 25 2024

@editor: Alycia Leonard, University of Oxford

Description of edits:
 - Cleaned up for integration in GeoNH3 repository
"""
import geopandas as gpd
import warnings

# Ignore all future warnings
warnings.simplefilter(action='ignore', category=FutureWarning)


hexagons = gpd.read_file('Data/hex_final.geojson')
hexagons.to_crs(epsg=4326, inplace=True)
world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres')) # may need to switch to higher res
countries = world.drop(columns=['pop_est', 'continent', 'iso_a3', 'gdp_md_est'])
countries = countries.rename(columns={'name':'country'})
hexagons_with_country = gpd.sjoin(hexagons, countries, op='intersects') # changed from "within"
hexagons_with_country.to_file('Data/hexagons_with_country.geojson', driver='GeoJSON')