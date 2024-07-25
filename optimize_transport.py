#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar 26 16:52:59 2023

@author: Claire Halloran, University of Oxford
Contains code originally written by Leander MÃ¼ller, RWTH Aachen University

Calculates the cost-optimal ammonia transportation strategy to the nearest demand center.

Calculate cost of trucking and pipeline transport
"""

import geopandas as gpd
import numpy as np
import pandas as pd
from functions import CRF, calculate_trucking_costs, calculate_pipeline_costs
from shapely.geometry import Point
import shapely.geometry
import shapely.wkt
import geopy.distance
import os
import json

#%% Data Input

# Excel file with technology parameters
technology_parameters = "Parameters/technology_parameters.xlsx"
demand_parameters = 'Parameters/demand_parameters.xlsx'
country_excel_path = 'Parameters/country_parameters.xlsx'

#%% load data from technology parameters Excel file

infra_data = pd.read_excel(technology_parameters,
                           sheet_name='Infra',
                           index_col='Infrastructure')

global_data = pd.read_excel(technology_parameters,
                            sheet_name='Global',
                            index_col='Parameter'
                            ).squeeze("columns")

water_data = pd.read_excel(technology_parameters,
                            sheet_name='Water',
                            index_col='Parameter'
                            ).squeeze("columns")
demand_center_list = pd.read_excel(demand_parameters,
                                   sheet_name='Demand centers',
                                   index_col='Demand center',
                                   )
country_parameters = pd.read_excel(country_excel_path,
                                    index_col='Country')

pipeline_construction = global_data['Pipeline construction allowed']
road_construction = global_data['Road construction allowed']

road_capex_long = infra_data.at['Long road','CAPEX']
road_capex_short = infra_data.at['Short road','CAPEX']
road_opex = infra_data.at['Short road','OPEX']

# Handle any hexagons at edges in the geojson which are labelled with a country we aren't analyzing

# Read the GeoJSON file
with open('Data/hexagons_with_country.geojson', 'r') as file:
    data = json.load(file)

# If the country of any hexagon is not in the country_parameters file, set the country to "Other" instead
for feature in data['features']:
    # Access and modify properties
    if not feature['properties']['country'] in list(country_parameters.index.values):
        feature['properties']['country'] = "Other"

# Write the modified GeoJSON back to the file
with open('Data/hexagons_with_country.geojson', 'w') as file:
    json.dump(data, file)

# Now, load the Hexagon file in geopandas
hexagon = gpd.read_file('Data/hexagons_with_country.geojson')

# Create Resources folder to save results if it doesn't already exist
if not os.path.exists('Resources'):
    os.makedirs('Resources')

#%% calculate cost of hydrogen state conversion and transportation for demand
# loop through all demand centers-- limit this on continential scale
for d in demand_center_list.index:
    demand_location = Point(demand_center_list.loc[d,'Lat [deg]'], demand_center_list.loc[d,'Lon [deg]'])
    distance_to_demand = np.empty(len(hexagon))
    hydrogen_quantity = demand_center_list.loc[d,'Annual demand [kg/a]']
    road_construction_costs = np.empty(len(hexagon))
    # trucking_states = np.empty(len(hexagon),dtype='<U10')
    trucking_costs = np.empty(len(hexagon))
    pipeline_costs = np.empty(len(hexagon))
    demand_fid = 0

# label demand location under consideration
    for i in range(len(hexagon)):
        if hexagon['geometry'][i].contains(demand_location) == True:
            demand_fid = i

    for i in range(len(hexagon)):
        # calculate distance to demand for each hexagon
        poly = shapely.wkt.loads(str(hexagon['geometry'][i]))
        center = poly.centroid
        demand_coords = (demand_center_list.loc[d,'Lat [deg]'], demand_center_list.loc[d,'Lon [deg]'])
        hexagon_coords = (center.y, center.x)
        dist = geopy.distance.geodesic(demand_coords, hexagon_coords).km
        
        distance_to_demand[i] = dist

        #!!! maybe this is the place to set a restriction based on distance to demand center-- for all hexagons with a distance below some cutoff point
        # label demand location under consideration
        if hexagon['geometry'][i].contains(demand_location) == True:
            local_conversion_cost = 0. # accounted for in ammonia plant optimization
            trucking_costs.append(0.)
            pipeline_costs.append(0.)
        
        # determine elec_cost at demand to determine potential energy costs
        # elec_costs_at_demand = float(hexagon['cheapest_elec_cost'][demand_fid])/1000
        # calculate cost of constructing a road to each hexagon
        if road_construction == True:
            if hexagon['road_dist'][i]==0:
                road_construction_costs[i] = 0.
            elif hexagon['road_dist'][i]!=0 and hexagon['road_dist'][i]<10:
                road_construction_costs[i] = hexagon['road_dist'][i]\
                    *road_capex_short*CRF(
                        country_parameters.loc[hexagon['country'][i],'Infrastructure interest rate'],
                        country_parameters.loc[hexagon['country'][i],'Infrastructure lifetime (years)'])\
                    +hexagon['road_dist'][i]*road_opex
            else:
                road_construction_costs[i] = hexagon['road_dist'][i]*road_capex_long*CRF(
                    country_parameters.loc[hexagon['country'][i],'Infrastructure interest rate'],
                    country_parameters.loc[hexagon['country'][i],'Infrastructure lifetime (years)'])\
                +hexagon['road_dist'][i]*road_opex
                
            trucking_cost = calculate_trucking_costs(
                                           distance_to_demand[i],
                                           hydrogen_quantity,
                                           country_parameters.loc[hexagon['country'][i],'Infrastructure interest rate'],
                                           "Parameters/transport_parameters.xlsx")
            
            
            trucking_costs[i] = trucking_cost

        elif hexagon['road_dist'][i]==0:
            trucking_cost = calculate_trucking_costs(
                                           distance_to_demand[i],
                                           hydrogen_quantity,
                                           country_parameters.loc[hexagon['country'][i],'Infrastructure interest rate'],
                                           "Parameters/transport_parameters.xlsx")
            
            trucking_costs[i] = trucking_cost

        elif hexagon['road_dist'][i]>0: 
            trucking_costs[i] = np.nan

        # pipeline costs
        if pipeline_construction== True:
            pipeline_cost, pipeline_type = calculate_pipeline_costs(distance_to_demand[i],
                                                                    hydrogen_quantity,
                                                                    country_parameters.loc[hexagon.country[i],'Electricity price (euros/kWh)'],
                                                                    country_parameters.loc[hexagon['country'][i],'Infrastructure interest rate']
                                                                    )
            pipeline_costs[i] = pipeline_cost
        else:
            pipeline_costs[i] = np.nan

    # variables to save for each demand scenario
    hexagon[f'{d} road construction costs'] = road_construction_costs/hydrogen_quantity
    hexagon[f'{d} trucking transport costs'] = trucking_costs # cost of road construction, supply conversion, trucking transport, and demand conversion
    # hexagon[f'{d} trucking state'] = trucking_states # cost of road construction, supply conversion, trucking transport, and demand conversion
    hexagon[f'{d} pipeline transport costs'] = pipeline_costs # cost of supply conversion, pipeline transport, and demand conversion

# Added force to UTF-8 encoding.
hexagon.to_file('Resources/hex_transport.geojson', driver='GeoJSON', encoding='utf-8')
