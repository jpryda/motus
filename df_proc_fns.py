import pandas as pd
from flask import session, abort

def filter_groups(df, filter_dict):
  for key_field, value_filter in filter_dict.items():
    if (len(df) == 0) or (value_filter is None) or (key_field in ['n','n_peak_intensity']):
      continue
    # "None" in the option menu for Parent Exercise has the value 'na'
    elif value_filter == 'na':
      df = df[df[key_field].isna()]
    # Extend to allow for OR multi-select capability if a list is specified
    elif type(value_filter) is list:
      # Multi column values
      # import pdb; pdb.set_trace()
      if isinstance(df[key_field].iloc[0], tuple) or isinstance(df[key_field].iloc[0], list):
        df = df[df.apply(lambda x: any(y in value_filter for y in x[key_field]), axis=1)]
      # Single column value
      else:
        df = df[df.apply(lambda x: x[key_field] in value_filter, axis=1)]
    # Single value only: checkbox
    else:
      df = df[df.apply(lambda x: value_filter == x[key_field], axis=1)]
  return(df)

def generate_workout(menu_df, exercise_filters):
  result_df = pd.DataFrame()
  for phase in exercise_filters:
    df = filter_groups(menu_df, phase)
    if len(result_df) > 0:
      df = df[~df.id.isin(result_df.id)] # avoid duplicates
    new_phase_df = df.sample(min(int(phase['n']), len(df)), replace=False)
    result_df=pd.concat([result_df, new_phase_df])
  return(result_df)

# def generate_workout_2(menu_df, exercise_filters, pinned_exercise_ids=[]):
#   result_df = pd.DataFrame()
#   processed_pinned_exercise_ids = []
#   raw_menu_df = menu_df

#   if len(pinned_exercise_ids) > 0:
#     # Exclude pinned exercises from sampling
#     pinned_df = menu_df[menu_df.id.isin(pinned_exercise_ids)]
#     result_df = pd.concat([result_df, pinned_df])
#     menu_df = menu_df[~menu_df.id.isin(pinned_exercise_ids)]

#   for idx, phase in enumerate(exercise_filters):
#     df_to_sample = filter_groups(menu_df, phase)
#     df_to_sample['input_row_idx'] = idx
#     # avoid duplicates between phase specifications
#     if len(result_df) > 0:
#       df_to_sample = df_to_sample[~df_to_sample.id.isin(result_df.id)]

#     df_to_check_pinned = filter_groups(raw_menu_df, phase)
#     # exclude from sampling if phase contains a pinned exercise and add to result_df
#     # keep pinned exercise exclusion within loop over exercise filters to subtract from the respective N supplied
#     if len(pinned_exercise_ids) > 0:
#       # Original problem
#       # [{'category': ['Pull'], 'n': 2}, {'category': ['Pull'], 'n': 2}], all pinned -> problem
#       # phase['n'] = 0,
#       # phase['n'] = 2, since we have added pinned exercises to result_df, removed from df_to_sample, pinned_df looks like 2 for second phase despite all pinned
#       # Would want to distribute somehow

#       # Would like to remove pinned exercises and deduct them from N across phases (ideally phase attribution?)
#       # With phase attribution of pinned exercise ids we would see phase 1 has 1 pinned exercise and so deduct 1 from phase['n']
#       # Without phase attribution, we see if pinned exercise _could_ be in phase 1 and if so deduct 1 from phase['n']
#       # If one pinned exercise could apply to multiple phases, must make a decision as to which phase to deduct!!
#       # However as we're looping through we're not sure what this relationship is when we pick the first two.
#       # If the third only applies to the first phase then we won't be deducting it from any other phase

#       # New problem
#       # Changing input filters doesn't clear pinned exercises
#       unseen_pinned_df = (
#           df_to_check_pinned[(df_to_check_pinned.id.isin(pinned_exercise_ids)) &
#                             ~(df_to_check_pinned.id.isin(processed_pinned_exercise_ids))]
#           .iloc[0:phase['n'], :] # only "select" up to n pinned ids for each phase, otherwise we will "deduct" all from the first pass in the case of overlapping
#       )

#       processed_pinned_exercise_ids = processed_pinned_exercise_ids + list(unseen_pinned_df.id)
#       phase['n'] = int(phase['n']) - len(unseen_pinned_df) # only subtract off those that are still False as haven't been selected prior

#     if 'n_peak_intensity' in phase:
#       peak_df = df_to_sample[df_to_sample.is_peak_intensity]
#       # Ensure that we still observe n if n_peak_intensity > n
#       peak_df = peak_df.sample(min(int(phase['n_peak_intensity']), len(peak_df), int(phase['n'])), replace=False)

#       non_peak_df = df_to_sample[~df_to_sample.is_peak_intensity]
#       remaining_non_peak_n = int(phase['n']) - len(peak_df)
#       non_peak_df = non_peak_df.sample(min(remaining_non_peak_n, len(non_peak_df)), replace=False)

#       new_phase_df = pd.concat([peak_df, non_peak_df])
#     else:
#       print(phase['n'])
#       print(processed_pinned_exercise_ids)
#       new_phase_df = df_to_sample.sample(min(int(phase['n']), len(df_to_sample)), replace=False)

#     result_df = pd.concat([result_df, new_phase_df])
#   return(result_df)

def sort_workout(new_workout_df):
  # Pull out max ring height when sorting in ascending order
  new_workout_df['first_ring_height'] = pd.Categorical(new_workout_df.apply(lambda x: x.ring_height[0] if len(x.ring_height) > 0 else x.ring_height, axis=1),
                                                  categories=['High','Med','Low'],
                                                  ordered=True)
  new_workout_df['second_ring_height'] = pd.Categorical(new_workout_df.apply(lambda x: x.ring_height[1] if len(x.ring_height) == 2 else tuple(), axis=1),
                                                  categories=['High','Med','Low'],
                                                  ordered=True)
  new_workout_sorted_df = (
      new_workout_df
      .sort_values(['first_ring_height','second_ring_height','is_peak_intensity'], ascending=[True, True, False])
      .drop(['first_ring_height','second_ring_height'], axis=1)
      .reset_index(drop=True)
      .reset_index()
      # .rename(columns={'index': '#'})
  )#[['id'] + ['input_row_idx','index','exercise','parent_exercise','category','is_peak_intensity','equipment','primary_muscle_groups','ring_height','intensities','tempo']]
  return(new_workout_sorted_df)

def fetch_pinned_workout(menu_df, pinned_exercise_ids):
    # pinned_df = menu_df[menu_df.id.isin(pinned_exercise_ids)]
    # Maintain order of ids passed in when selecting rows. Could just set id as index
    pinned_df = menu_df.iloc[pd.Index(menu_df['id']).get_indexer(pinned_exercise_ids)]

    # Set to dummies since `output_column_names` contains these
    pinned_df['index'] = list(range(len(pinned_df)))
    pinned_df['input_row_idx'] = 0

    # Store several variables in a secure cookie session
    print('Session Variables')
    # Store the latest exercise ids sent to the user in a cookie rather than in HTML (could just keep this cached on the server)
    session['new_workout_ids'] = list(pinned_df['id'])
    # Store the categories that were generated to include in the output DB name
    session['categories'] = list(pinned_df['category'])
    # Could more cleanly pass in `[output_column_names]` and add in 'pin' element

    print(pinned_df[['id','input_row_idx','index','exercise','parent_exercise','category','is_peak_intensity','equipment','primary_muscle_groups','ring_height','intensities','tempo']])
    return(pinned_df)

# Expect `pinned_exercise_dict` to be columnar and of the form {id: [id_vals], input_row_idx: [idx_vals]}
def generate_workout(menu_df, exercise_filters, to_sort=True, pinned_exercise_dict={}):
  result_df = pd.DataFrame()

  for idx, phase in enumerate(exercise_filters):
    df_to_sample = filter_groups(menu_df, phase)
    df_to_sample['input_row_idx'] = idx
    # avoid duplicates between phase specifications
    if len(result_df) > 0:
      df_to_sample = df_to_sample[~df_to_sample.id.isin(result_df.id)]
    # exclude from sampling if phase contains a pinned exercise and add to result_df

    specified_pinned_df = pd.DataFrame(pinned_exercise_dict)
    if len(specified_pinned_df) > 0:
      specified_pinned_phase_df = specified_pinned_df[specified_pinned_df.input_row_idx == idx]
      if len(specified_pinned_phase_df) > 0:
        # only want pinned exercises that fall within what the input filters specified
        # i.e. if inputs filters are changed such that they exclude a pinned exercise it *shouldn't* persist
        df_pinned_sampled = df_to_sample[df_to_sample.id.isin(specified_pinned_phase_df.id)]
        df_to_sample = df_to_sample[~df_to_sample.id.isin(specified_pinned_phase_df.id)]
        result_df = pd.concat([result_df, df_pinned_sampled])
        phase['n'] = phase['n'] - len(df_pinned_sampled)
        if 'n_peak_intensity' in phase:
          phase['n_peak_intensity'] = phase['n_peak_intensity'] - len(df_pinned_sampled[df_pinned_sampled.is_peak_intensity])

    if 'n_peak_intensity' in phase:
      peak_df = df_to_sample[df_to_sample.is_peak_intensity]
      # Ensure that we still observe n if n_peak_intensity > n
      peak_df = peak_df.sample(min(phase['n_peak_intensity'], len(peak_df), phase['n']), replace=False)

      non_peak_df = df_to_sample[~df_to_sample.is_peak_intensity]
      remaining_non_peak_n = phase['n'] - len(peak_df)
      non_peak_df = non_peak_df.sample(min(remaining_non_peak_n, len(non_peak_df)), replace=False)

      new_phase_df = pd.concat([peak_df, non_peak_df])
    else:
      new_phase_df = df_to_sample.sample(min(phase['n'], len(df_to_sample)), replace=False)
    result_df = pd.concat([result_df, new_phase_df])

  if len(result_df) == 0:
    abort(404)

  # Sort workout
  if(to_sort):
    result_df = sort_workout(result_df)

  # Store several variables in a secure cookie session
  print('Session Variables')
  # Store the latest exercise ids sent to the user in a cookie rather than in HTML (could just keep this cached on the server)
  session['new_workout_ids'] = list(result_df['id'])
  # Store the categories that were generated to include in the output DB name
  session['categories'] = list(result_df['category'])
  # Could more cleanly pass in `[output_column_names]` and add in 'pin' element
  print(result_df[['id','input_row_idx','index','exercise','parent_exercise','category','is_peak_intensity','equipment','primary_muscle_groups','ring_height','intensities','tempo']])
  return(result_df)

# def save_session_vars(new_workout_df):
#   # Store several variables in a secure cookie session
#   print('Session Variables')
#   # Store the latest exercise ids sent to the user in a cookie rather than in HTML (could just keep this cached on the server)
#   session['new_workout_ids'] = list(new_workout_df['id'])
#   # Store the categories that were generated to include in the output DB name
#   session['categories'] = list(new_workout_df['category'])

# def generate_and_sort_workout(preprocessed_menu_df, exercise_filters, pinned_exercise_dict={}):
#   new_workout = generate_workout_3(preprocessed_menu_df, exercise_filters, pinned_exercise_dict)
#   # if len(new_workout) == 0:
#   #   abort(404)
#   new_workout_sorted = sort_workout(new_workout)

#   # # Store several variables in a secure cookie session
#   # print('Session Variables')
#   # # Store the latest exercise ids sent to the user in a cookie rather than in HTML (could just keep this cached on the server)
#   # session['new_workout_ids'] = list(new_workout_sorted['id'])
#   # # Store the categories that were generated to include in the output DB name
#   # session['categories'] = list(new_workout_sorted['category'])

#   print('Sorted workout DF')
#   # Could more cleanly pass in `[output_column_names]` and add in 'pin' element
#   print(new_workout_sorted[['pin','id','input_row_idx','index','exercise','parent_exercise','category','is_peak_intensity','equipment','primary_muscle_groups','ring_height','intensities','tempo']])
#   return(new_workout_sorted)

# Formatting functions to better present HTML table
def to_snake_case(text):
  return(text.lower().replace(' ','_'))

def to_title_case(text):
  return(text.title().replace('_',' '))

def tuple_quotes_fmttr(x):
  return(str(x).replace("'", "")
               .replace("(","")
               .replace(")","") if len(x) > 0 else '')

# def empty_tuple_fmttr(x):
#   return('' if len(x) == 0 else x)

def produce_workout_table_html(df, menu_db_base_url, output_column_names, pinned_exercise_ids=[]):
  df['exercise'] = (
    df.apply(lambda x: f"<a href='{menu_db_base_url}{x.id.replace('-','')}' target='_blank' class='link-dark'><span style='font-weight:bold'>{x.exercise}</span></a>"
    , axis=1)
  )
  df['index'] = df['index'] + 1 # Start at 0
  df['pin'] = (
    df.apply(lambda x: '<input type="checkbox" class="form-check-input" checked>'
                        if x.id in pinned_exercise_ids
                        else '<input type="checkbox" class="form-check-input">'
    , axis=1)
  )
  df = df[output_column_names].rename(columns={'index': '#'})
  df.columns = df.columns.str.title().str.replace('_',' ')
  return(
    # '<hr> ' +
    df.to_html( classes = 'table table-striped table-sm',
                index=False,
                header=True,
                justify='match-parent',
                border = 0,
                na_rep = '',
                formatters={
                  to_title_case('equipment'): tuple_quotes_fmttr,
                  to_title_case('primary_muscle_groups'): tuple_quotes_fmttr,
                  to_title_case('category'): tuple_quotes_fmttr,
                  to_title_case('intensities'): tuple_quotes_fmttr,
                  to_title_case('ring_height'): tuple_quotes_fmttr
                },
                render_links=True,
                escape=False,
                table_id = 'outputTable')
    )

def json_results_to_df(db_query_results):
  # Convert json results to a DF for ease of filtering
  menu_db_query_all = pd.json_normalize(db_query_results)
  chosen_fields = [ 'id',
                    'properties.Exercise.title',
                    'properties.Parent Exercise.select.name',
                    'properties.Is Peak Intensity.checkbox',
                    'properties.Equipment.multi_select',
                    'properties.Category.multi_select',
                    'properties.Primary Muscle Groups.multi_select',
                    'properties.Intensities.multi_select',
                    'properties.Ring Height.multi_select',
                    'properties.Tempo.rich_text']
  menu_db_query_all_slct = menu_db_query_all[chosen_fields]

  # Create tuples for multi-select fields
  menu_db_query_all_slct['equipment'] = menu_db_query_all_slct.apply(lambda x: tuple(sorted([x['name'] for x in x['properties.Equipment.multi_select']])), axis=1)
  menu_db_query_all_slct['primary_muscle_groups'] = menu_db_query_all_slct.apply(lambda x: tuple(sorted([x['name'] for x in x['properties.Primary Muscle Groups.multi_select']])), axis=1)
  menu_db_query_all_slct['category'] = menu_db_query_all_slct.apply(lambda x: tuple(sorted([x['name'] for x in x['properties.Category.multi_select']])), axis=1)
  menu_db_query_all_slct['intensities'] = menu_db_query_all_slct.apply(lambda x: tuple(sorted([x['name'] for x in x['properties.Intensities.multi_select']])), axis=1)
  menu_db_query_all_slct['ring_height'] = menu_db_query_all_slct.apply(lambda x: tuple(sorted([x['name'] for x in x['properties.Ring Height.multi_select']])), axis=1)
  menu_db_query_all_slct['parent_exercise'] = menu_db_query_all_slct['properties.Parent Exercise.select.name']
  menu_db_query_all_slct['exercise'] = menu_db_query_all_slct['properties.Exercise.title'].apply(lambda x: x[0]['plain_text'] if len(x) > 0 else '')
  menu_db_query_all_slct['is_peak_intensity'] = menu_db_query_all_slct['properties.Is Peak Intensity.checkbox']
  menu_db_query_all_slct['tempo'] = menu_db_query_all_slct['properties.Tempo.rich_text'].apply(lambda x: x[0]['plain_text'] if len(x) > 0 else '')

  return(menu_db_query_all_slct)

default_exercise_filters = [
  {
    "n" : 6
  }
]

## "category" : ["Push"],
## "equipment" : ["Rings", "Ground"],
## "primary_muscle_groups" : ["Chest"],
## "parent_exercise": None,
## "is_peak_intensity" : None,
## "n" : 3
# default_exercise_filters = [
#   {
#     "category" : ["Push"],
#     "equipment" : ["Rings"],
#     "primary_muscle_groups" : ["Chest", "Triceps"],
#     "n" : 2
#   },
#   {
#     "category" : ["Pull"],
#     "equipment" : ["Rings", "High Bar"],
#     "primary_muscle_groups" : ["Biceps"],
#     "n" : 2
#   },
#     {
#     "category" : ["Movement"],
#     "n" : 1
#   },
#     {
#     "category" : ["Legs"],
#     "n" : 1
#   }
# ]
