
import pandas as pd
import numpy as np
import math

def CRF(interest,lifetime):
    '''
    Calculates the capital recovery factor of a capital investment.

    Parameters
    ----------
    interest : float
        interest rate.
    lifetime : float or integer
        lifetime of asset.

    Returns
    -------
    CRF : float
        present value factor.

    '''
    interest = float(interest)
    lifetime = float(lifetime)

    CRF = (((1+interest)**lifetime)*interest)/(((1+interest)**lifetime)-1)
    return CRF

transport_excel_path = "Parameters/transport_parameters.xlsx"

def calculate_trucking_costs(distance, quantity, interest, excel_path):
    '''
    calculates the annual cost of transporting hydrogen by truck.

    Parameters
    ----------
    distance : float
        distance between hydrogen production site and demand site.
    quantity : float
        annual amount of hydrogen to transport.
    interest : float
        interest rate on capital investments.
    excel_path : string
        path to transport_parameters.xlsx file
        
    Returns
    -------
    cost_per_unit : float
        annual cost of ammonia transport per kilogram of ammonia.
    '''
    daily_quantity = quantity/365
    transport_parameters = pd.read_excel(excel_path,
                                         sheet_name = 'NH3',
                                         index_col = 'Parameter'
                                         ).squeeze('columns')

    average_truck_speed = transport_parameters['Average truck speed (km/h)']                #km/h
    working_hours = transport_parameters['Working hours (h/day)']                     #h/day
    diesel_price = transport_parameters['Diesel price (euros/L)']                    #€/l
    costs_for_driver = transport_parameters['Costs for driver (euros/h)']                  #€/h
    working_days = transport_parameters['Working days (per year)']                      #per year
    max_driving_dist = transport_parameters['Max driving distance (km/a)']               #km/a Maximum driving distance per truck per year

    spec_capex_truck = transport_parameters['Spec capex truck (euros)']               #€
    spec_opex_truck = transport_parameters['Spec opex truck (% of capex/a)']                  #% of CAPEX/a
    diesel_consumption = transport_parameters['Diesel consumption (L/100 km)']                 #l/100km
    truck_lifetime = transport_parameters['Truck lifetime (a)']                      #a

    spec_capex_trailor = transport_parameters['Spec capex trailer (euros)']
    spec_opex_trailor =transport_parameters['Spec opex trailer (% of capex/a)']
    net_capacity = transport_parameters['Net capacity (kg NH3)']                     #kgh2
    trailor_lifetime = transport_parameters['Trailer lifetime (a)']                   #a
    loading_unloading_time = transport_parameters['Loading unloading time (h)']            #hours 


    # max_day_dist = max_driving_dist/working_days
    amount_deliveries_needed = daily_quantity/net_capacity
    deliveries_per_truck = working_hours/(loading_unloading_time+(2*distance/average_truck_speed))
    trailors_needed = round((amount_deliveries_needed/deliveries_per_truck)+0.5,0)
    # total_drives_day = round(amount_deliveries_needed+0.5,0) # not in ammonia calculation
    trucks_needed = trailors_needed

    capex_trucks = trucks_needed * spec_capex_truck
    capex_trailor = trailors_needed * spec_capex_trailor
    # capex_total = capex_trailor + capex_trucks
    # this if statement seems suspect to me-- how can a fractional number of deliveries be completed?
    if amount_deliveries_needed < 1:
        fuel_costs = (amount_deliveries_needed*2*distance*365/100)*diesel_consumption*diesel_price
        wages = amount_deliveries_needed * ((distance/average_truck_speed)*2+loading_unloading_time) * working_days * costs_for_driver
    
    else:
        fuel_costs = (round(amount_deliveries_needed+0.5)*2*distance*365/100)*diesel_consumption*diesel_price
        wages = round(amount_deliveries_needed+0.5) * ((distance/average_truck_speed)*2+loading_unloading_time) * working_days * costs_for_driver
    annual_costs = (capex_trucks*CRF(interest,truck_lifetime)+capex_trailor*CRF(interest,trailor_lifetime))\
        + capex_trucks*spec_opex_truck + capex_trailor*spec_opex_trailor + fuel_costs + wages
    cost_per_unit = annual_costs/quantity
    return cost_per_unit

#Only new pipelines
pipeline_excel_path = "Parameters/pipeline_parameters.xlsx"

def calculate_pipeline_costs(distance,quantity,elec_cost,interest):
    '''
    calculates the annualized cost of building a pipeline.

    Parameters
    ----------
    distance : float
        distance from production site to demand site in km.
    quantity : float
        annual quantity of hydrogen demanded in kg.
    elec_cost : float
        price of electricity along pipeline in euros.
    interest : float
        interest rate on capital investments.

    Returns
    -------
    cost_per_unit : float
        annual costs for pipeline per kilogram of ammonia transported.
    string
        size of pipeline to build

    '''
    quantity = quantity / 1000 # convert kg to t
    all_parameters = pd.read_excel(pipeline_excel_path,
                                   sheet_name='All',
                                    index_col = 'Parameter'
                                    ).squeeze('columns')
    opex = all_parameters['Opex (% of capex)']
    availability = all_parameters['Availability']
    lifetime_pipeline = all_parameters['Pipeline lifetime (a)']
    # lifetime_compressors = all_parameters['Compressor lifetime (a)']
    electricity_demand = all_parameters['Electricity demand (kWh/kg*km)']
    large_max_flow = all_parameters['Large pipeline max capacity (t NH3/a)']*availability
    large_min_flow = all_parameters['Large pipeline min capacity (t NH3/a)']*availability # t to kg
    med_min_flow = all_parameters['Medium pipeline min capacity (t NH3/a)']*availability # t to kg
    small_min_flow = all_parameters['Small pipeline min capcity (t NH3/a)']*availability # t to kg
    # if demand is large enough, split flow into multiple pipelines
    if quantity > large_max_flow:
        n_pipelines = math.ceil(quantity/large_max_flow)
        quantity_per_pipeline = quantity / n_pipelines
    else:
        n_pipelines = 1
        quantity_per_pipeline = quantity
        
    if quantity_per_pipeline >= small_min_flow and quantity_per_pipeline < med_min_flow:
        pipeline_type = 'Small'
    
    elif quantity_per_pipeline >= med_min_flow and quantity_per_pipeline < large_min_flow:
        pipeline_type = 'Medium'
    
    elif quantity_per_pipeline >= large_min_flow and quantity_per_pipeline <= large_max_flow:
        pipeline_type = 'Large'
    
    elif quantity_per_pipeline < small_min_flow:
        return np.nan,'Flow too small for pipeline'
    
    pipeline_parameters = pd.read_excel(pipeline_excel_path,
                                   sheet_name=pipeline_type,
                                    index_col = 'Parameter'
                                    ).squeeze('columns')
    y_int = pipeline_parameters['Capex y-intercept (€/t/yr/100km)']
    print(y_int)
    slope = pipeline_parameters['Capex flow coefficient (€/t^2/yr^2/100km)']
    print(slope)
    capex_coeff = (y_int + slope*quantity_per_pipeline)
    print(capex_coeff)
    capex_annual = (n_pipelines*(capex_coeff*distance/100*quantity_per_pipeline)*CRF(interest,lifetime_pipeline)) # distance coefficients are per 100 km
    opex_annual = opex*n_pipelines*(capex_coeff*distance/100*quantity_per_pipeline)
    electricity_costs = electricity_demand * distance * quantity * elec_cost

    annual_costs = capex_annual + opex_annual + electricity_costs
    cost_per_unit = annual_costs/(quantity*1000) # convert back to kg
    return cost_per_unit, f"{pipeline_type} Pipeline"
