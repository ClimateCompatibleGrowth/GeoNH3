#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 26 11:47:57 2023

@author: Claire Halloran, University of Oxford

Includes code from Nicholas Salmon, University of Oxford, for optimizing
hydrogen and ammonia plant capacity.
"""

import atlite
import geopandas as gpd
import pypsa
import pandas as pd
import p_auxiliary as aux
from functions import CRF
import numpy as np
import logging
import time
import warnings

# Ignore all deprecation warnings and future warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.simplefilter(action='ignore', category=FutureWarning)

logging.basicConfig(level=logging.ERROR)


def demand_schedule(quantity, transport_excel_path, weather_excel_path, freq='H'):
    '''
    calculates hourly ammonia demand for truck shipment and pipeline transport.

    Parameters
    ----------
    quantity : float
        annual amount of ammonia to transport in kilograms.
    transport_excel_path : string
        path to transport_parameters.xlsx file
    weather_excel_path : string
        path to transport_parameters.xlsx file
    freq : offset string, optional
        pandas-style offset string for demand schedule frequency. Default is "H".

    Returns
    -------
    trucking_hourly_demand_schedule : pandas DataFrame
        hourly demand profile for hydrogen trucking.
    pipeline_hourly_demand_schedule : pandas DataFrame
        hourly demand profile for pipeline transport.
    '''
    transport_parameters = pd.read_excel(transport_excel_path,
                                         sheet_name='NH3',
                                         index_col='Parameter'
                                         ).squeeze('columns')
    weather_parameters = pd.read_excel(weather_excel_path,
                                       index_col='Parameters',
                                       ).squeeze('columns')
    truck_capacity = transport_parameters['Net capacity (kg NH3)']
    start_date = weather_parameters['Start date']
    end_date = weather_parameters['End date (not inclusive)']

    # schedule for trucking
    annual_deliveries = quantity / truck_capacity
    quantity_per_delivery = quantity / annual_deliveries
    index = pd.date_range(start_date, end_date, periods=annual_deliveries)
    trucking_demand_schedule = pd.DataFrame(quantity_per_delivery, index=index, columns=['Demand'])
    # first create hourly schedule
    trucking_hourly_demand_schedule = trucking_demand_schedule.resample('H').sum().fillna(0.)
    # then resample to desired frequency using mean
    trucking_demand_resampled_schedule = trucking_hourly_demand_schedule.resample(freq).mean()

    # schedule for pipeline
    index = pd.date_range(start_date, end_date, freq=freq)
    pipeline_hourly_quantity = quantity / index.size
    pipeline_hourly_demand_schedule = pd.DataFrame(pipeline_hourly_quantity, index=index, columns=['Demand'])
    # resample pipeline schedule
    pipeline_demand_resampled_schedule = pipeline_hourly_demand_schedule.resample(freq).mean()
    return trucking_demand_resampled_schedule, pipeline_demand_resampled_schedule


# in the future, may want to make hexagons a class with different features
def optimize_ammonia_plant(wind_potential, pv_potential, demand_profile,
                           wind_max_capacity, pv_max_capacity,
                           country_series, water_limit=None):
    '''
   Optimizes the size of green ammonia plant components based on renewable potential, ammonia demand, and country parameters.

    Parameters
    ----------
    wind_potential : xarray DataArray
        1D dataarray of per-unit wind potential in hexagon.
    pv_potential : xarray DataArray
        1D dataarray of per-unit solar potential in hexagon.
    demand_profile : pandas DataFrame
        hourly dataframe of ammonia demand in kg.
    country_series : pandas Series
        interest rate and lifetime information.
    water_limit : float
        annual limit on water available for electrolysis in hexagon, in cubic meters. Default is None.

    Returns
    -------
    lcoa : float
        levelized cost per kg ammonia.
    wind_capacity: float
        optimal wind capacity in MW.
    solar_capacity: float
        optimal solar capacity in MW.
    electrolyzer_capacity: float
        optimal electrolyzer capacity in MW.
    battery_capacity: float
        optimal battery storage capacity in MWh.
    h2_storage: float
        optimal hydrogen storage capacity in MWh.
    nh3_storage: float
        optimal ammonia storage capacity in MWh.

    '''

    # Set up network
    # Import a generic network
    n = pypsa.Network(override_component_attrs=aux.create_override_components())

    # Set the time values for the network
    n.set_snapshots(demand_profile.index)
    demand_profile['weights'] = 8760 / len(n.snapshots)
    n.snapshot_weightings = demand_profile['weights']

    # if a water limit is given, check if hydrogen demand can be met
    if water_limit != None:
        # total ammonia demand in kg
        total_ammonia_demand = (
                    (n.loads_t.p_set['Ammonia demand'] * n.snapshot_weightings['objective']).sum() / 6.25 * 1000)
        # total hydrogen demand in kg
        total_hydrogen_demand = total_ammonia_demand * 17 / 3  # convert kg ammonia to kg H2
        # check if hydrogen demand can be met based on hexagon water availability
        water_constraint = total_hydrogen_demand <= water_limit * 111.57  # kg H2 per cubic meter of water
        # note that this constraint is purely stoichiometric-- more water may be needed for cooling or other processes
        if water_constraint == False:
            print('Not enough water to meet hydrogen demand!')
            # return null values
            lcoa = np.nan
            wind_capacity = np.nan
            solar_capacity = np.nan
            electrolyzer_capacity = np.nan
            battery_capacity = np.nan
            h2_storage = np.nan
            return lcoa, wind_capacity, solar_capacity, electrolyzer_capacity, battery_capacity, h2_storage

    # Import the design of the H2 plant into the network
    n.import_from_csv_folder("Parameters/Basic_ammonia_plant")

    # Import demand profile
    # Note: All flows are in MW or MWh, conversions for hydrogen done using HHVs. Hydrogen HHV = 39.4 MWh/t
    # Note: All flows are in MW or MWh, conversions for ammonia done using HHVs. Ammonia HHV = 6.25 MWh/t
    # hydrogen_demand = pd.read_excel(demand_path,index_col = 0) # Excel file in kg hydrogen, convert to MWh
    n.add('Load',
          'Ammonia demand',
          bus='Ammonia',
          p_set=demand_profile['Demand'].to_numpy() / 1000 * 6.25,
          )
    # Send the weather data to the model
    n.generators_t.p_max_pu['Wind'] = wind_potential
    n.generators_t.p_max_pu['Solar'] = pv_potential

    # specify maximum capacity based on land use
    n.generators.loc['Wind', 'p_nom_max'] = wind_max_capacity
    n.generators.loc['Solar', 'p_nom_max'] = pv_max_capacity

    # specify technology-specific and country-specific WACC and lifetime here
    n.generators.loc['Wind', 'capital_cost'] = n.generators.loc['Wind', 'capital_cost'] \
                                               * CRF(country_series['Wind interest rate'],
                                                     country_series['Wind lifetime (years)'])
    n.generators.loc['Solar', 'capital_cost'] = n.generators.loc['Solar', 'capital_cost'] \
                                                * CRF(country_series['Solar interest rate'],
                                                      country_series['Solar lifetime (years)'])
    for item in [n.links, n.stores]:
        item.capital_cost = item.capital_cost * CRF(country_series['Plant interest rate'],
                                                    country_series['Plant lifetime (years)'])
    n.links.loc['HydrogenCompression', 'marginal_cost'] = 0.0001  # Just stops pointless cycling through storage

    # Adjust the capital cost of the stores and the marginal costs based on temporal aggregation
    # n.stores.capital_cost *= 8760/len(n.snapshots)
    # n.links.marginal_cost *= 8760/len(n.snapshots)

    # Solve the model
    solver = 'gurobi'
    n.lopf(solver_name=solver,
           solver_options={'LogToConsole': 0, 'OutputFlag': 0},
           pyomo=True,
           extra_functionality=aux.pyomo_constraints,
           )
    # Output results
    lcoa = n.objective / ((n.loads_t.p_set['Ammonia demand'] * n.snapshot_weightings[
        'objective']).sum() / 6.25 * 1000)  # convert back to kg NH3
    wind_capacity = n.generators.p_nom_opt['Wind']
    solar_capacity = n.generators.p_nom_opt['Solar']
    electrolyzer_capacity = n.links.p_nom_opt['Electrolysis']
    battery_capacity = n.stores.e_nom_opt['Battery']
    h2_storage = n.stores.e_nom_opt['CompressedH2Store']
    # !!! need to save ammonia storage capacity as well
    nh3_storage = n.stores.e_nom_opt['Ammonia']
    print('LCOA: €' + str(lcoa) + '/kg NH3')
    return lcoa, wind_capacity, solar_capacity, electrolyzer_capacity, battery_capacity, h2_storage, nh3_storage


# set model frequency-- can downsample to reduce solve time

freq = '3H'

transport_excel_path = "Parameters/transport_parameters.xlsx"
weather_excel_path = "Parameters/weather_parameters.xlsx"
country_excel_path = 'Parameters/country_parameters.xlsx'
technology_parameters = "Parameters/technology_parameters.xlsx"

country_parameters = pd.read_excel(country_excel_path,
                                   index_col='Country')
demand_excel_path = 'Parameters/demand_parameters.xlsx'
demand_parameters = pd.read_excel(demand_excel_path,
                                  index_col='Demand center',
                                  ).squeeze("columns")
demand_centers = demand_parameters.index
weather_parameters = pd.read_excel(weather_excel_path,
                                   index_col='Parameters'
                                   ).squeeze('columns')
weather_filename = weather_parameters['Filename']
global_data = pd.read_excel(technology_parameters,
                            sheet_name='Global',
                            index_col='Parameter'
                            ).squeeze("columns")
pipeline_construction = global_data['Pipeline construction allowed']

# !!! can include water costs here instead of in water_cost.py
# water_data = pd.read_excel(technology_parameters,
#                             sheet_name='Water',
#                             index_col='Parameter'
#                             ).squeeze("columns")
# water_spec_cost = water_data['Water specific cost (euros/m3)']

hexagons = gpd.read_file('Resources/hex_transport.geojson')
# !!! change to name of cutout in weather
cutout = atlite.Cutout('Cutouts/' + weather_filename + '.nc')
layout = cutout.uniform_layout()

pv_profile = cutout.pv(
    panel='CSi',
    orientation='latitude_optimal',
    layout=layout,
    shapes=hexagons,
    per_unit=True
).resample(time=freq).mean()
pv_profile = pv_profile.rename(dict(dim_0='hexagon'))

wind_profile = cutout.wind(
    # Changed turbine type - was Vestas_V80_2MW_gridstreamer in first run
    # Other option being explored: NREL_ReferenceTurbine_2020ATB_4MW, Enercon_E126_7500kW
    turbine='NREL_ReferenceTurbine_2020ATB_4MW',
    layout=layout,
    shapes=hexagons,
    per_unit=True
).resample(time=freq).mean()
wind_profile = wind_profile.rename(dict(dim_0='hexagon'))

for location in demand_centers:
    lcoas_trucking = np.zeros(len(pv_profile.hexagon))
    solar_capacities = np.zeros(len(pv_profile.hexagon))
    wind_capacities = np.zeros(len(pv_profile.hexagon))
    electrolyzer_capacities = np.zeros(len(pv_profile.hexagon))
    battery_capacities = np.zeros(len(pv_profile.hexagon))
    h2_storages = np.zeros(len(pv_profile.hexagon))
    nh3_storages = np.zeros(len(pv_profile.hexagon))

    print('Optimizing for trucking demand profile...')
    start = time.process_time()
    # function
    for hexagon in pv_profile.hexagon.data:
        ammonia_demand_trucking, ammonia_demand_pipeline = demand_schedule(
            demand_parameters.loc[location, 'Annual demand [kg/a]'],
            transport_excel_path,
            weather_excel_path,
            freq=freq)
        country_series = country_parameters.loc[hexagons.country[hexagon]]
        lcoa, wind_capacity, solar_capacity, electrolyzer_capacity, battery_capacity, h2_storage, nh3_storage = \
            optimize_ammonia_plant(wind_profile.sel(hexagon=hexagon, time=ammonia_demand_trucking.index),
                                   pv_profile.sel(hexagon=hexagon, time=ammonia_demand_trucking.index),
                                   ammonia_demand_trucking,
                                   hexagons.loc[hexagon, 'theo_turbines'],
                                   hexagons.loc[hexagon, 'theo_pv'],
                                   country_series,
                                   # water_limit = hexagons.loc[hexagon,'delta_water_m3']
                                   )
        lcoas_trucking[hexagon] = lcoa
        solar_capacities[hexagon] = solar_capacity
        wind_capacities[hexagon] = wind_capacity
        electrolyzer_capacities[hexagon] = electrolyzer_capacity
        battery_capacities[hexagon] = battery_capacity
        h2_storages[hexagon] = h2_storage
        nh3_storages[hexagon] = nh3_storage

    trucking_time = time.process_time() - start

    hexagons[f'{location} trucking solar capacity'] = solar_capacities
    hexagons[f'{location} trucking wind capacity'] = wind_capacities
    hexagons[f'{location} trucking electrolyzer capacity'] = electrolyzer_capacities
    hexagons[f'{location} trucking battery capacity'] = battery_capacities
    hexagons[f'{location} trucking H2 storage capacity'] = h2_storages
    hexagons[f'{location} trucking NH3 storage capacity'] = nh3_storages
    # save trucking lcoa
    hexagons[f'{location} trucking production cost'] = lcoas_trucking

    print('Trucking optimisation complete! Time elapsed: ' + str(trucking_time) + ' s')
    if pipeline_construction == True:

        # calculate cost of production for pipeline demand profile
        lcoas_pipeline = np.zeros(len(pv_profile.hexagon))
        solar_capacities = np.zeros(len(pv_profile.hexagon))
        wind_capacities = np.zeros(len(pv_profile.hexagon))
        electrolyzer_capacities = np.zeros(len(pv_profile.hexagon))
        battery_capacities = np.zeros(len(pv_profile.hexagon))
        h2_storages = np.zeros(len(pv_profile.hexagon))
        nh3_storages = np.zeros(len(pv_profile.hexagon))
        print('Optimizing for pipeline demand profile...')
        start = time.process_time()
        for hexagon in pv_profile.hexagon.data:
            ammonia_demand_trucking, ammonia_demand_pipeline = demand_schedule(
                demand_parameters.loc[location, 'Annual demand [kg/a]'],
                transport_excel_path,
                weather_excel_path,
                freq=freq)
            country_series = country_parameters.loc[hexagons.country[hexagon]]
            lcoa, wind_capacity, solar_capacity, electrolyzer_capacity, battery_capacity, h2_storage, nh3_storage = \
                optimize_ammonia_plant(wind_profile.sel(hexagon=hexagon, time=ammonia_demand_pipeline.index),
                                       pv_profile.sel(hexagon=hexagon, time=ammonia_demand_pipeline.index),
                                       ammonia_demand_pipeline,
                                       hexagons.loc[hexagon, 'theo_turbines'],
                                       hexagons.loc[hexagon, 'theo_pv'],
                                       country_series,
                                       # water_limit = hexagons.loc[hexagon,'delta_water_m3'],
                                       )
            lcoas_pipeline[hexagon] = lcoa
            solar_capacities[hexagon] = solar_capacity
            wind_capacities[hexagon] = wind_capacity
            electrolyzer_capacities[hexagon] = electrolyzer_capacity
            battery_capacities[hexagon] = battery_capacity
            h2_storages[hexagon] = h2_storage
            nh3_storages[hexagon] = nh3_storage
    else:
        solar_capacities = np.empty(len(hexagons)).fill(np.nan)
        wind_capacities = np.empty(len(hexagons)).fill(np.nan)
        electrolyzer_capacities = np.empty(len(hexagons)).fill(np.nan)
        battery_capacities = np.empty(len(hexagons)).fill(np.nan)
        h2_storages = np.empty(len(hexagons)).fill(np.nan)
        nh3_storages = np.empty(len(hexagons)).fill(np.nan)

    pipeline_time = time.process_time() - start
    print('Pipeline optimisation complete! Time elapsed: ' + str(pipeline_time) + ' s')

    hexagons[f'{location} pipeline solar capacity'] = solar_capacities
    hexagons[f'{location} pipeline wind capacity'] = wind_capacities
    hexagons[f'{location} pipeline electrolyzer capacity'] = electrolyzer_capacities
    hexagons[f'{location} pipeline battery capacity'] = battery_capacities
    hexagons[f'{location} pipeline H2 storage capacity'] = h2_storages
    hexagons[f'{location} pipeline NH3 storage capacity'] = nh3_storages

    # add optimal lcoa for each hexagon to hexagon file
    hexagons[f'{location} pipeline production cost'] = lcoas_pipeline

hexagons.to_file('Resources/hex_lcoa.geojson', driver='GeoJSON', encoding='utf-8')

