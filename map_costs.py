#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 27 11:14:48 2023

@author: Claire Halloran, University of Oxford

This script visualizes the spatial cost of ammonia for each demand center.

Edited on Thu Jul 25 2024

@editor: Alycia Leonard, University of Oxford

Description of edits:
 - Fixed up labels (LCOA instead of LCOH)
"""

import geopandas as gpd
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
import pandas as pd

hexagons = gpd.read_file('Resources/hex_total_cost.geojson')
demand_excel_path = 'Parameters/demand_parameters.xlsx'
demand_parameters = pd.read_excel(demand_excel_path,
                                  index_col='Demand center',
                                  )

demand_centers = demand_parameters.index
#%% plot LCOA for each hexagon
# update central coordinates for area considered
crs = ccrs.Orthographic(central_longitude = 37.5, central_latitude= 0.0)
for demand_center in demand_centers:
    
    fig = plt.figure(figsize=(10,5))
    
    ax = plt.axes(projection=crs)
    ax.set_axis_off()
    
    hexagons.to_crs(crs.proj4_init).plot(
        ax=ax,
        column = f'{demand_center} trucking production cost',
        legend = True,
        cmap = 'viridis_r',
        legend_kwds={'label':'Production LCOA [euros/kg]'},
        missing_kwds={
            "color": "lightgrey",
            "label": "Missing values",
        },    
    )
    ax.set_title(f'{demand_center} trucking production cost')
    fig.savefig(f'Resources\\{demand_center} trucking production cost.png', bbox_inches='tight')
    
    fig = plt.figure(figsize=(10,5))
    
    ax = plt.axes(projection=crs)
    ax.set_axis_off()
    
    hexagons.to_crs(crs.proj4_init).plot(
        ax=ax,
        column = f'{demand_center} pipeline production cost',
        legend = True,
        cmap = 'viridis_r',
        legend_kwds={'label':'Production LCOA [euros/kg]'},
        missing_kwds={
            "color": "lightgrey",
            "label": "Missing values",
        },    
    )
    ax.set_title(f'{demand_center} pipeline production cost')
    fig.savefig(f'Resources\\{demand_center} pipeline production cost.png', bbox_inches='tight')

    #%% plot transportation costs
    fig = plt.figure(figsize=(10,5))
    
    ax = plt.axes(projection=crs)
    ax.set_axis_off()
    
    
    hexagons[f'{demand_center} total trucking cost'] =\
        hexagons[f'{demand_center} trucking transport costs']+hexagons[f'{demand_center} road construction costs']
    
    hexagons.to_crs(crs.proj4_init).plot(
        ax=ax,
        column = f'{demand_center} total trucking cost',
        legend = True,
        cmap = 'viridis_r',
        legend_kwds={'label':'Trucking cost [euros/kg]'},
        missing_kwds={
            "color": "lightgrey",
            "label": "Missing values",
        },    
    )
    ax.set_title(f'{demand_center} trucking transport costs')
    fig.savefig(f'Resources\\{demand_center} trucking transport cost.png', bbox_inches='tight')
    
    fig = plt.figure(figsize=(10,5))
    
    ax = plt.axes(projection=crs)
    ax.set_axis_off()
    
    hexagons.to_crs(crs.proj4_init).plot(
        ax=ax,
        column = f'{demand_center} pipeline transport costs',
        legend = True,
        cmap = 'viridis_r',
        legend_kwds={'label':'Pipeline cost [euros/kg]'},
        missing_kwds={
            "color": "lightgrey",
            "label": "Missing values",
        },    
    )
    ax.set_title(f'{demand_center} pipeline transport costs')
    fig.savefig(f'Resources\\{demand_center} pipeline transport cost.png', bbox_inches='tight')

    # %% plot total costs

    fig = plt.figure(figsize=(10,5))
    
    ax = plt.axes(projection=crs)
    ax.set_axis_off()
    
    hexagons.to_crs(crs.proj4_init).plot(
        ax=ax,
        column = f'{demand_center} trucking total cost',
        legend = True,
        cmap = 'viridis_r',
        legend_kwds={'label':'LCOA [euros/kg]'},
        missing_kwds={
            "color": "lightgrey",
            "label": "Missing values",
        },    
    )
    ax.set_title(f'{demand_center} trucking LCOA')
    fig.savefig(f'Resources\\{demand_center} trucking LCOA.png', bbox_inches='tight')
    
    crs = ccrs.Orthographic(central_longitude = 37.5, central_latitude= 0.0)
    
    fig = plt.figure(figsize=(10,5))
    
    ax = plt.axes(projection=crs)
    ax.set_axis_off()
    
    hexagons.to_crs(crs.proj4_init).plot(
        ax=ax,
        column = f'{demand_center} pipeline total cost',
        legend = True,
        cmap = 'viridis_r',
        legend_kwds={'label':'LCOA [euros/kg]'},
        missing_kwds={
            "color": "lightgrey",
            "label": "Missing values",
        },    
    )
    ax.set_title(f'{demand_center} pipeline LCOA')
    fig.savefig(f'Resources\\{demand_center} pipeline LCOA.png', bbox_inches='tight')

    
    fig = plt.figure(figsize=(10,5))
    
    ax = plt.axes(projection=crs)
    ax.set_axis_off()
    
    hexagons.to_crs(crs.proj4_init).plot(
        ax=ax,
        column = f'{demand_center} lowest cost',
        legend = True,
        cmap = 'viridis_r',
        legend_kwds={'label':'LCOA [euros/kg]'},
        missing_kwds={
            "color": "lightgrey",
            "label": "Missing values",
        },    
    )
    ax.set_title(f'{demand_center} LCOA')
    fig.savefig(f'Resources\\{demand_center} LCOA.png', bbox_inches='tight')
# %% plot water costs

fig = plt.figure(figsize=(10,5))

ax = plt.axes(projection=crs)
ax.set_axis_off()

hexagons.to_crs(crs.proj4_init).plot(
    ax=ax,
    column = 'Ocean water costs',
    legend = True,
    cmap = 'viridis_r',
    legend_kwds={'label':'Water cost [euros/kg H2]'},
    missing_kwds={
        "color": "lightgrey",
        "label": "Missing values",
    },    
)
ax.set_title('Ocean water costs')
fig.savefig(f'Resources\\Ocean water costs.png', bbox_inches='tight')

fig = plt.figure(figsize=(10,5))

ax = plt.axes(projection=crs)
ax.set_axis_off()

hexagons.to_crs(crs.proj4_init).plot(
    ax=ax,
    column = 'Freshwater costs',
    legend = True,
    cmap = 'viridis_r',
    legend_kwds={'label':'Water cost [euros/kg H2]'},
    missing_kwds={
        "color": "lightgrey",
        "label": "Missing values",
    },    
)
ax.set_title('Freshwater costs')
fig.savefig(f'Resources\\Freshwater costs.png', bbox_inches='tight')

