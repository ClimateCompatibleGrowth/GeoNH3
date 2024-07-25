import pypsa
import numpy as np
import pyomo.environ as pm
import logging
import pandas as pd

# !!! define time step in hours here
timestep = 3

def create_override_components():
    """Set up new component attributes as required"""
    # Modify the capacity of a link so that it can attach to 2 buses.
    override_component_attrs = pypsa.descriptors.Dict(
        {k: v.copy() for k, v in pypsa.components.component_attrs.items()}
    )

    override_component_attrs["Link"].loc["bus2"] = [
        "string",
        np.nan,
        np.nan,
        "2nd bus",
        "Input (optional)",
    ]
    override_component_attrs["Link"].loc["efficiency2"] = [
        "static or series",
        "per unit",
        1.0,
        "2nd bus efficiency",
        "Input (optional)",
    ]
    override_component_attrs["Link"].loc["p2"] = [
        "series",
        "MW",
        0.0,
        "2nd bus output",
        "Output",
    ]
    return override_component_attrs


def get_col_widths(dataframe):
    # First we find the maximum length of the index column
    idx_max = max([len(str(s)) for s in dataframe.index.values] + [len(str(dataframe.index.name))])
    # Then, we concatenate this to the max of the lengths of column name and its values for each column, left to right
    return [idx_max] + [max([len(str(s)) for s in dataframe[col].values] + [len(col)]) for col in dataframe.columns]


def get_weather_data(file_name=None, aggregation_count=None):
    """Asks the user where the weather data is, and pulls it in. Keeps asking until it gets a file.
    If a file_name has already been provided this code just imports the data. """
    # import data
    if file_name is None:
        input_check = True
        while input_check:
            try:
                input_check = False
                file = input("What is the name of your weather data file? "
                             "It must be a CSV, but don't include the file extension >> ")
                weather_data = pd.read_csv(file + '.csv')
                weather_data.drop(weather_data.columns[0], axis=1, inplace=True)
            except FileNotFoundError:
                input_check = True
                print("There's no input file there! Try again.")

        # Check the weather data is a year long
        if len(weather_data) < 8700 or len(weather_data) > 8760 + 48:
            logging.warning('Your weather data seems not to be one year long in hourly intervals. \n'
                            'Are you sure the input data is correct?'
                            ' If not, exit the code using ctrl+c and start again.')

    else:
        weather_data = pd.read_csv(file_name)
        weather_data.drop(weather_data.columns[0], axis=1, inplace=True)

        # Just tidy up the data if it needs it...
        # if 'Grid' not in weather_data.columns and 'Grid in ':
        #     weather_data['Grid'] = np.zeros(len(weather_data))
        # if 'RampDummy' not in weather_data.columns:
        #     weather_data['RampDummy'] = np.ones(len(weather_data))

    if aggregation_count is not None:
        print('Aggregating weather data...')
        weather_data = aggregate_data(weather_data, aggregation_count)
        return weather_data
    else:
        return weather_data


def aggregate_data(data, aggregation_count):
    """Aggregates self.concat into blocks of fixed numbers of size aggregation_count.
    aggregation_count must be an integer which is a factor of 24 (i.e. 1, 2, 3, 4, 6, 12, 24)"""
    if len(data) % aggregation_count != 0:
        raise TypeError("Aggregation counter must divide evenly into the total number of data points")

    df = pd.Series(range(len(data) // aggregation_count)).to_frame('snapshot').set_index('snapshot')

    for column in data.columns:
        if np.average(data[column]) > 0:
            df[column] = [np.average(data[column].to_list()[i * aggregation_count:(i + 1) * aggregation_count])
                          for i in df.index]
        else:
            df[column] = np.zeros(len(df))
    return df


def check_CAPEX(file_name=None):
    """Checks if the user has put the CAPEX into annualised format. If not, it helps them do so.
    file_name is the weather data file - if it is not specified the user is asked.
    Otherwise, this function does nothing."""
    if file_name is None:
        check = input('Are your capital costs in the generators.csv, '
                      'components.csv and stores.csv files annualised?'
                      '\n (i.e. have you converted them from their upfront capital cost'
                      ' to the cost that accrues each year under the chosen financial conditions? \n'
                      '(Y/N) >> ')
    else:
        check = 'Y'
    if check != 'Y':
        print('You have selected no annualisation, which means you have entered the upfront capital cost'
              ' of the equipment. \n We have to ask you a few questions to convert these to annualised costs.')
        check2 = True
        while check2:
            try:
                discount = float(input('Enter the weighted average cost of capital in percent (i.e. 7 not 0.07)'))
                years = float(input('Enter the plant operating years.'))
                O_and_M = float(input('Enter the fixed O & M costs as a percentage of installed CAPEX '
                                      '(i.e. 2 not 0.02)'))
                check2 = False
            except ValueError:
                logging.warning('You have to enter a number! Try again.')
                check2 = True

        crf = discount * (1 + discount) ** years / ((1 + discount) ** years - 1)
        if crf < 2 or crf > 20 or O_and_M < 0 or O_and_M > 8:
            print('Your financial parameter inputs are giving some strange results. \n'
                  'You might want to exit the code using ctrl + c and try re-entering them.')

        return crf, O_and_M
    else:
        if file_name is None:
            print('You have selected the annualised capital cost entry. \n'
                  'Make sure that the annualised capital cost data includes any operating costs that you '
                  'estimate based on plant CAPEX.')
        return None


def get_solving_info(file_name=None):
    """Prompts the user for information about the solver and the problem formulation.
    If no file_name is provided then the model will autoselect gurobi and pyomo."""
    if file_name is None:
        solver = input('What solver would you like to use? '
                       'If you leave this blank, the glpk default will be used >> ')
        if solver == '':
            solver = 'glpk'

        formulator = 'p'
        print('In this code, the only option for solving is to use pyomo,'
              ' because additional constraints have been turned on. ')
    else:
        solver = 'gurobi'
        formulator = 'p'
    return solver, formulator


def get_scale(n, file_name=None):
    """Gives the user some information about the solution, and asks if they'd like it to be scaled.
    If the file_name is prespecified the scale is automatically 1 (i.e. no scaling)"""
    if file_name is None:
        print('\nThe unscaled generation capacities are:')
        print(n.generators.rename(columns={'p_nom_opt': 'Rated Capacity (MW)'})[['Rated Capacity (MW)']])
        print('The unscaled hydrogen production is {a} t/year\n'.format(a=n.loads.p_set.values[0] / 39.4 * 8760))
        scale = input('Enter a scaling factor for the results, to adjust the production. \n'
                      "If you don't want to scale the results, enter a value of 1 >> ")
        try:
            scale = float(scale)
        except ValueError:
            scale = 1
            print("You didn't enter a number! The results won't be scaled.")
        return scale
    else:
        return 1


def get_results_dict_for_excel(n, scale, aggregation_count=1, operating=False, time_step=1.0):
    """Takes the results and puts them in a dictionary ready to be sent to Excel"""
    # Rename the components:
    links_name_dct = {'p_nom_opt': 'Rated Capacity (MW)',
                      'carrier': 'Carrier',
                      'bus0': 'Primary Energy Source',
                      'bus2': 'Secondary Energy Source'}
    comps = n.links.rename(columns=links_name_dct)[[i for i in links_name_dct.values()]]
    comps["Rated Capacity (MW)"] *= scale

    # Get the energy flows
    primary = n.links_t.p0 * scale
    secondary = (n.links_t.p2 * scale).drop(columns=['HydrogenFromStorage', 'Electrolysis', 'BatteryInterfaceIn',
                                                     'BatteryInterfaceOut', 'HydrogenFuelCell'])

    # Rescale the energy flows (I know there's hard coding here but these numbers should never change!):
    primary['HydrogenCompression'] /= 39.4
    primary['HydrogenFromStorage'] /= 39.4
    primary['HydrogenFuelCell'] *= n.links.loc['HydrogenFuelCell'].efficiency
    secondary['HB'] /= 39.4
    primary['Ammonia production (t/h)'] = secondary['HB'] / 0.18
    
    # Rename the energy flows so that the units are comprehensible
    primary.rename(columns={
        'Electrolysis': 'Electrolysis (MW)',
        'HydrogenCompression': 'Hydrogen to storage (t/h)',
        'HydrogenFromStorage': 'Hydrogen from storage (t/h)',
        'BatteryInterfaceIn': 'Battery Charge (MW)',
        'BatteryInterfaceOut': 'Battery Discharge (MW)',
        'HydrogenFuelCell': 'Power from Fuel cell (MW)',
        'HB': 'HB Power consumption (MW)'
    }, inplace=True)
    secondary.rename(columns={'HydrogenCompression': 'H2 Compression Power Consumption (MW)',
                              'HB': 'HB Hydrogen consumption (t/h)'}, inplace=True)

    consumption = pd.merge(primary, secondary, left_index=True, right_index=True)

    # # Just move the penalty link column to the end...
    # cols = list(consumption.columns)
    # cols.append(cols.pop(cols.index('PenaltyLink')))
    # consumption = consumption.reindex(columns=cols)

    output = {
        'Headlines': pd.DataFrame({
            'Objective function (USD/t)': [n.objective / (n.loads.p_set.values[0] / 6.25 * 8760)],
            'Production (t/year)': n.loads.p_set.values[0] / 6.25 * 8760 * scale}, index=['LCOA (USD/t)']),
        'Generators': n.generators.rename(columns={'p_nom_opt': 'Rated Capacity (MW)'})[
                          ['Rated Capacity (MW)']] * scale,
        'Components': comps,
        'Stores': scale * aggregation_count * time_step * n.stores.rename(columns={
                                        'e_nom_opt': 'Storage Capacity (MWh)'})[['Storage Capacity (MWh)']],
        'Energy generation (MW)': n.generators_t.p * scale,
        'Energy consumption': consumption,
        'Stored energy capacity (MWh)': n.stores_t.e * scale * aggregation_count * time_step
    }

    if operating:
        years = len(n.stores_t.e['Ammonia'])/8760
        objective = n.stores_t.e['Ammonia'].iloc[-1]/6.25*1E-6/years
        output['Headlines'] = pd.DataFrame({
            'Annual Production (t/year)': [objective]}, index=['Production (MMTPA)'])
    return output


def write_results_to_excel(output, file_name="", extension=""):
    """Takes results dictionary and puts them in an Excel file. User determines the file name"""
    if file_name is None:
        incomplete = True
        while incomplete:
            output_file = input("Enter the name of your output data file. \n"
                                "Don't include the file extension. >> ") + '.xlsx'
            try:
                incomplete = False
                with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
                    for key in output.keys():
                        dataframe = output[key]
                        dataframe.to_excel(writer, sheet_name=key)
                        worksheet = writer.sheets[key]
                        for i, width in enumerate(get_col_widths(dataframe)):
                            worksheet.set_column(i, i, width)
            except PermissionError:
                incomplete = True
            print('There is a problem writing on that file. Try another excel file name.')
    else:
        output_file = r'Results/' + file_name.split('\\')[-1][:-4] + extension + '.xlsx'
        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            for key in output.keys():
                dataframe = output[key]
                dataframe.to_excel(writer, sheet_name=key)
                worksheet = writer.sheets[key]
                for i, width in enumerate(get_col_widths(dataframe)):
                    worksheet.set_column(i, i, width)


def get_results_dict_for_multi_site(n, aggregation_count=1, operating=False, time_step=1.0):
    """Just a simpler function that only gets the headline information, and nothing to do with times"""
    dct = dict()
    if not operating:
        dct['Objective'] = n.objective / (n.loads.p_set.values[0] / 6.25 * 8760 * 1000)
    else:
        years = len(n.stores_t.e['Ammonia'])/8784
        dct['Objective'] = n.stores_t.e['Ammonia'].iloc[-1]/6.25*1E-6/years
    for generator in n.generators.index.to_list():
        dct[generator] = n.generators.loc[generator, 'p_nom_opt']
    for component in n.links.index.to_list():
        dct[component] = n.links.loc[component, 'p_nom_opt']
    for store in n.stores.index.to_list():
        dct[store] = n.stores.loc[store, 'e_nom_opt'] * aggregation_count * time_step
    dct['Hydrogen Storage (t)'] = n.stores.loc[
                                          'CompressedH2Store', 'e_nom_opt'] * aggregation_count * time_step / 39.4
    return dct


def extra_functionalities(n, snapshots):
    """Could be added later if you wanted to convert the pyomo constraints to linopt, but this is a pain."""
    pass

# !!! need to manually change timedelta here when resampling

def _nh3_ramp_down(model, t):
    """Places a cap on how quickly the ammonia plant can ramp down"""
    # if t == 0:
    if t == model.t.at(1):

        old_rate = model.link_p['HB', model.t.at(-1)]
    else:
        # old_rate = model.link_p['HB', t - 1]
        old_rate = model.link_p['HB', t - pd.Timedelta(timestep, unit = 'H')]

    return old_rate - model.link_p['HB', t] <= \
        model.link_p_nom['HB'] * model.HB_max_ramp_down
    # Note 20 is the UB of the size of the ammonia plant; essentially if x = 0 then the constraint is not active


def _nh3_ramp_up(model, t):
    """Places a cap on how quickly the ammonia plant can ramp down"""
    # if t == 0:
    if t == model.t.at(1):
        old_rate = model.link_p['HB', model.t.at(-1)]
    else:
        # old_rate = model.link_p['HB', t - 1]
        old_rate = model.link_p['HB', t - pd.Timedelta(timestep, unit = 'H')]


    return model.link_p['HB', t] - old_rate <= \
        model.link_p_nom['HB'] * model.HB_max_ramp_up


def _nh3_ramp_down_operating(model, t):
    """Places a cap on how quickly the ammonia plant can ramp down"""
    # if t == 0:
    if t == model.t.at(1):
        old_rate = model.link_p['HB', model.t.at(-1)]
    else:
        # old_rate = model.link_p['HB', t - 1]
        old_rate = model.link_p['HB', t - pd.Timedelta(timestep, unit = 'H')]


    return old_rate - model.link_p['HB', t] <= \
        model.HB_capacity * model.HB_max_ramp_down
    # Note 20 is the UB of the size of the ammonia plant; essentially if x = 0 then the constraint is not active


def _nh3_ramp_up_operating(model, t):
    """Places a cap on how quickly the ammonia plant can ramp down"""
    # if t == 0:
    if t == model.t.at(1):
        old_rate = model.link_p['HB', model.t.at(-1)]
    else:
        # old_rate = model.link_p['HB', t - 1]
        old_rate = model.link_p['HB', t - pd.Timedelta(timestep, unit = 'H')]


    return model.link_p['HB', t] - old_rate <= \
        model.HB_capacity * model.HB_max_ramp_up



def _penalise_ramp_down(model, t):
    """Places a cap on how quickly the ammonia plant can ramp down"""
    if t == model.t.at(1):
    # if t == 0:
        old_rate = model.link_p['HB', model.t.at(-1)]
    else:
        # old_rate = model.link_p['HB', t - 1]
        old_rate = model.link_p['HB', t - pd.Timedelta(1, unit = 'H')]


    return model.link_p['PenaltyLink', t] >= (old_rate - model.link_p['HB', t])


def _penalise_ramp_up(model, t):
    """Places a cap on how quickly the ammonia plant can ramp down"""
    if t == model.t.at(1):
    # if t == 0:
        old_rate = model.link_p['HB', model.t.at(-1)]
    else:
        # old_rate = model.link_p['HB', t - 1]
        old_rate = model.link_p['HB', t - pd.Timedelta(1, unit = 'H')]


    return model.link_p['PenaltyLink', t] >= (model.link_p['HB', t] - old_rate)


def pyomo_constraints(network, snapshots):
    """Includes a series of additional constraints which make the ammonia plant work as needed:
    i) Battery sizing
    ii) Ramp hard constraints down (Cannot be violated)
    iii) Ramp hard constraints up (Cannot be violated)
    iv) Ramp soft constraints down
    v) Ramp soft constraints up
    (iv) and (v) just softly suppress ramping so that the model doesn't 'zig-zag', which looks a bit odd on operation.
    Makes very little difference on LCOA. """

    # The battery constraint is built here - it doesn't need a special function because it doesn't depend on time
    network.model.battery_interface = pm.Constraint(
        rule=lambda model: network.model.link_p_nom['BatteryInterfaceIn'] ==
                           network.model.link_p_nom['BatteryInterfaceOut'] /
                           network.links.efficiency["BatteryInterfaceOut"])

    # Constrain the maximum discharge of the H2 storage relative to its size
    time_step_cycle = 4/8760*timestep*0.5  # Factor 0.5 for 3 hour time step, 0.5 for oversized storage
    network.model.cycling_limit = pm.Constraint(
        rule=lambda model: network.model.link_p_nom['BatteryInterfaceOut'] ==
                           network.model.store_e_nom['CompressedH2Store'] * time_step_cycle)

    # The HB Ramp constraints are functions of time, so we need to create some pyomo sets/parameters to represent them.
    network.model.t = pm.Set(initialize=network.snapshots)
    network.model.HB_max_ramp_down = pm.Param(initialize=network.links.loc['HB'].ramp_limit_down)
    network.model.HB_max_ramp_up = pm.Param(initialize=network.links.loc['HB'].ramp_limit_up)

    # Using those sets/parameters, we can now implement the constraints...
    logging.warning('Pypsa has been overridden - Ramp rates on NH3 plant are included')
    network.model.NH3_pyomo_overwrite_ramp_down = pm.Constraint(network.model.t, rule=_nh3_ramp_down)
    network.model.NH3_pyomo_overwrite_ramp_up = pm.Constraint(network.model.t, rule=_nh3_ramp_up)
    # network.model.NH3_pyomo_penalise_ramp_down = pm.Constraint(network.model.t, rule=_penalise_ramp_down)
    # network.model.NH3_pyomo_penalise_ramp_up = pm.Constraint(network.model.t, rule=_penalise_ramp_up)

def pyomo_operating_constraints(network, snapshots):
    """Exactly as per the other constraints, but excludes any constraints which only apply during design"""
    # The HB Ramp constraints are functions of time, so we need to create some pyomo sets/parameters to represent them.
    network.model.t = pm.Set(initialize=network.snapshots)
    network.model.HB_max_ramp_down = pm.Param(initialize=network.links.loc['HB'].ramp_limit_down)
    network.model.HB_max_ramp_up = pm.Param(initialize=network.links.loc['HB'].ramp_limit_up)
    network.model.HB_capacity = pm.Param(initialize=network.links.loc['HB'].p_nom_opt)

    # Using those sets/parameters, we can now implement the constraints...
    logging.warning('Pypsa has been overridden - Ramp rates on NH3 plant are included')
    network.model.NH3_pyomo_overwrite_ramp_down = pm.Constraint(network.model.t, rule=_nh3_ramp_down_operating)
    network.model.NH3_pyomo_overwrite_ramp_up = pm.Constraint(network.model.t, rule=_nh3_ramp_up_operating)


def convert_network_to_operating(n, ammonia_cost_per_ton=500, aggregation_count=1, file_name="", multi_site=False,
                                 time_step=1.0):
    """Takes a designed network built with the designer and fixes the parameters as needs be
    ammonia_cost_per_ton = the cost at which ammonia will be sold; this gives the model a reason to make ammonia"""

    # Sets the expandable parameters to false:
    n.links.p_nom_extendable = [False for _ in range(len(n.links))]
    n.stores.e_nom_extendable = [False for _ in range(len(n.stores))]
    n.generators.p_nom_extendable = [False for _ in range(len(n.generators))]

    # Sets the basic equipment size to its optimum size from the last run...
    n.links.p_nom = n.links.p_nom_opt
    n.stores.e_nom = n.stores.e_nom_opt
    n.generators.p_nom = n.generators.p_nom_opt

    # Sets the ammonia storage to be very cheap and expandable - it's just a measure of production
    n.stores.loc['Ammonia', 'capital_cost'] = 0.001
    n.stores.loc['Ammonia', 'e_nom_extendable'] = True
    n.stores.loc['Ammonia', 'e_nom_max'] = 1E9
    n.stores.loc['Ammonia', 'e_cyclic'] = False
    n.stores.loc['Ammonia', 'e_initial'] = 0


    # Sets the marginal cost of ammonia production to be negative so the system makes a profit...
    n.links.loc['HB', 'marginal_cost'] = -ammonia_cost_per_ton/6.25*time_step*aggregation_count/10  # 10 is no. of years in dataset

    # Turns the ammonia load off:
    n.loads.loc['Ammonia', 'p_set'] = 0

    # Adjust the maximum allowable operating rate of the ammonia plant...
    n.links_t.p_max_pu = aggregate_data(
        pd.read_csv('HB_p_max_pu.csv').set_index('snapshot').rename(columns={'HB_Max': 'HB'}), aggregation_count)

    # Re-solves model:
    n.lopf(solver_name='gurobi', pyomo=True, extra_functionality=pyomo_operating_constraints)

    if not multi_site:
        detailed_results = get_results_dict_for_excel(n, 1, aggregation_count, operating=True, time_step=time_step)
        write_results_to_excel(detailed_results, file_name=file_name, extension="_operating")
        results = get_results_dict_for_multi_site(n, aggregation_count, operating=True, time_step=time_step)
    else:
        results = get_results_dict_for_multi_site(n, aggregation_count, operating=True, time_step=time_step)

    return results

