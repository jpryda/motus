# app/routes.py

import random
import logging
import sys
import os
from datetime import date
import time
import asyncio
# import json

from app import app
from flask import render_template, request, session
from flask import jsonify, redirect, url_for
from requests_oauthlib import OAuth2Session
from notion_client import Client, AsyncClient
import pandas as pd
# from oauthlib.common import urldecode

from .df_proc_fns import *

# Set Flask secret key to created a signed cookie used by the Flask session
app.secret_key = 'calisthenics_yzzki6thSyyK!CPY'

authorization_base_url = 'https://api.notion.com/v1/oauth/authorize'
token_url = 'https://api.notion.com/v1/oauth/token'

# If running locally (`source app/.env; export FLASK_ENV=development; python -m flask run`)
if app.config['ENV'] == 'development':
  # This information is obtained upon registration of a new Notion Integration
  CLIENT_ID = os.getenv("LOCAL_NOTION_CLIENT_ID")
  CLIENT_SECRET = os.getenv("LOCAL_NOTION_CLIENT_SECRET")
  # In case FLASK_DEBUG is overwritten to 0 set this value
  # app.config['DEBUG'] = True
  # app.config['AUTHLIB_INSECURE_TRANSPORT'] = True # Doesn't seem to work
  logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
  INCLUDE_CHILD_BLOCKS = False
# Flask otherwise will default app.config['ENV'] to 'production'
else:
  CLIENT_ID = os.getenv("PROD_NOTION_CLIENT_ID")
  CLIENT_SECRET = os.getenv("PROD_NOTION_CLIENT_SECRET")
  INCLUDE_CHILD_BLOCKS = True

# Root page for DB push
# calisthenics_logging_framework_page_id = '95502915-cb82-4915-86c2-86ea37e291b8'
ORDER_PROPERTY_NAME = 'Order'

def yt_url_expander(video_url):
  short_url = 'youtu.be/'
  long_url = 'www.youtube.com/watch?v='
  if short_url in video_url:
    return(video_url.replace(short_url, long_url))
  else:
    return(video_url)

def flatten(l): return flatten(l[0]) + (flatten(l[1:]) if len(l) > 1 else []) if type(l) is list else [l]

def list_of_dicts_to_dict(l): return dict((k, v) for result in l for k, v in result.items())

async def get_page_blocks(client, page_id):
  page_block_results = (await client.blocks.children.list(page_id))['results']
  # print(page_block_results)

  # Post-process results: Expand YT URLs, fetch content for synced blocks
  if len(page_block_results) > 0:
    # Expand YT video URLs otherwise Notion throws a fit and says the URL is invalid
    for idx, block_dict in enumerate(page_block_results):
      if 'video' in block_dict:
        block_dict['video']['external']['url'] = yt_url_expander(block_dict['video']['external']['url'])
      if 'synced_block' in block_dict:
        if block_dict['synced_block']['synced_from'] is None:
          id_to_fetch_children = block_dict['id']
        else:
          id_to_fetch_children = block_dict['synced_block']['synced_from']['block_id']
          page_block_results[idx] = (await client.blocks.children.list(id_to_fetch_children))['results']

    # Flatten if list contains a nested list caused by a synced block e.g. [{}, [{},{}]] -> [{},{},{}]
    if any([isinstance(x, list) for x in page_block_results]):
      print("Flattening")
      page_block_results = flatten(page_block_results)
  return({page_id: page_block_results})

async def init_all():
  # Set private Notion integration used to
  ## 1) Query pages in entire DB
  ## 2) Query blocks in entire DB
  ## 3) Fetch Menu DB schema
  print(f'init_all asyncio.all_tasks() {asyncio.all_tasks()}')

  notion_priv_async = AsyncClient(auth=os.getenv("NOTION_INTERNAL_SECRET"))
  source_menu_db_id = '9f2761e5-a1c1-4987-ae85-f8e4d4a37f8e'

  async with notion_priv_async as client:
    # Init DB
    menu_db_query = await client.databases.query(database_id = source_menu_db_id)
    print("Getting DB Source")
    # Convert json results to a Pandas DF for ease of filtering (see functions in df_proc_fns.py)
    menu_db_query_slct_df = json_results_to_df(menu_db_query['results'])
    exercise_page_ids = menu_db_query_slct_df['id'].tolist()

    # Init DB schema. Should be user changeable in future.
    menu_db_schema = await client.databases.retrieve(database_id = source_menu_db_id)

    # Init blocks
    if INCLUDE_CHILD_BLOCKS:
      blocks_get_task_list = [get_page_blocks(client, page_id) for page_id in exercise_page_ids]
      print(f"Getting blocks for {len(exercise_page_ids)} pages")
      # blocks_results: {original page id: {block json}} format
      blocks_results = await asyncio.gather(*blocks_get_task_list)
      page_id_blocks_mapping = list_of_dicts_to_dict(blocks_results)
    else:
      page_id_blocks_mapping = dict()

    return(menu_db_query, menu_db_query_slct_df, menu_db_schema, page_id_blocks_mapping)

# Create the Event Loop - https://stackoverflow.com/questions/47841985/make-a-python-asyncio-call-from-a-flask-route
menu_db_query, menu_db_query_slct_df, menu_db_schema, page_id_blocks_mapping = asyncio.run(init_all())

def construct_json_rows_for_upload(menu_db_query_results, selected_ids, types_to_ignore):
  # Package data in an appropriate format Notion expects: pull straight from results and filter based on generated workout
  # This pulls ALL fields, not just those selected in new_workout

  # Can also delete all ids from menu_db_query['results'] and time fields
  # for k,v in tst_kv.items():
  #   if 'id' in v:
  #     del v['id']
  #   if v['type'] == 'multi_select':
  #     for x in v['multi_select']:
  #       del x['id']
  #   if v['type'] == 'last_edited_time':
  #     del k

  row_list_to_upload = []
  for row in menu_db_query_results:
    if row['id'] not in list(selected_ids):
      continue

    row_dict = {'original_id': row['id']}
    for k,v in row['properties'].items():
      # Ignore relation cols for now
      if v['type'] in types_to_ignore:
        print("Skipped " + v['type'] + ": ", k, v)
        continue
      if v['type'] == 'multi_select':
        row_dict[k] = {'multi_select': [{'name': x['name']} for x in v['multi_select']] }
      elif v['type'] == 'select':
        if v['select'] is None:
          print("Skipped select: ", k, v)
          continue
        else:
          row_dict[k] = {'select': {'name': v['select']['name']}}
      elif v['type'] == 'rich_text':
        if len(v['rich_text']) > 0:
          row_dict[k] = {'rich_text': [{'text': {'content': x['text']['content']} for x in v['rich_text']}]}
      elif v['type'] == 'checkbox':
        row_dict[k] = {'checkbox': v['checkbox']}
      elif v['type'] == 'title':
        row_dict[k] = {'title': [{'text': {'content': x['text']['content']}} for x in v['title']]}

    # Finally add the order as specified by the index of the id of the generated workout
    # row_dict[ORDER_PROPERTY_NAME] = session['new_workout_ids'].index(row['id'])
    row_dict[ORDER_PROPERTY_NAME] = {'number': session['new_workout_ids'].index(row['id']) + 1}
    row_list_to_upload.append(row_dict)

  # Sort according to order of generated new_workout. Negate to ensure first is inserted at the end to be at the top (if syncrhonous)
  row_list_to_upload = sorted(row_list_to_upload, key = lambda x: -x[ORDER_PROPERTY_NAME]['number'])
  # Remove Order key
  # row_list_to_upload = [{k:v for k,v in x.items() if k != 'Order'} for x in row_list_to_upload]
  return(row_list_to_upload)

calisthenics_menu_base_url = 'https://pear-knight-937.notion.site/'
calisthenics_menu_public_url = calisthenics_menu_base_url + '9f2761e5a1c14987ae85f8e4d4a37f8e?v=8445b310230a40b7bd4ae2ca0d92bd8d'

options_key_order = ['category','equipment','parent_exercise'] # 'is_peak_intensity','primary_muscle_groups'
output_column_names = ['order','pin','exercise','category','is_peak_intensity','equipment','ring_height','tempo','intensities','primary_muscle_groups','input_row_idx','id']

@app.route("/")
def default_workout():
    default_workout_df = generate_and_sort_workout(menu_db_query_slct_df, default_exercise_filters)
    # Retrieve DB options
    # The ordering of options can be set by adjusting them in the Notion UI
    options_dict = {}
    for k, v in menu_db_schema['properties'].items():
      if v['type'] in ['multi_select','select']:
        field_type = v['type']
        # Set values to snake case
        options_dict[to_snake_case(k)] = [x['name'] for x in v[field_type]['options']]
    options_dict['is_peak_intensity'] = [True, False]

    # Fieldnames are capitalised in Notion
    options_dict_ordered = {k:options_dict[k] for k in options_key_order if k in options_dict}
    input_column_names = [k for k in options_key_order] + ['n','n_peak_intensity']

    return render_template(
      'index.html',
      title='Motus',
      input_column_names=input_column_names,
      options_data=list(options_dict_ordered.values()),
      new_workout_table = produce_workout_table_html(default_workout_df, calisthenics_menu_base_url, output_column_names),
      calisthenics_menu_public_url=calisthenics_menu_public_url,
      total_num_exercises = len(menu_db_query['results'])
    )

def process_input_filters(exercise_filters_raw):
  print("Raw input json")
  print(exercise_filters_raw)

  # Unused dropdown options are not sent
  exercise_filters_user_set_snake_keys = [ {to_snake_case(k):v for k,v in x.items()} for x in exercise_filters_raw ]
  exercise_filters_user_set = [ {k : int(v) if k in ['n','n_peak_intensity']
                                            else v == 'True' if k == 'is_peak_intensity'
                                            else 'na' if v == 'na'
                                            # else v if k in ['parent_exercise','exercise'] # old logic for lists -> NaNs messes up df.apply(lambda x: any(y in value_filter for y in x[key_field]), axis=1)
                                            else [v] # List to match DF tuples: equipment, primary_muscle_groups, category, intensities, ring_height
                                  for k,v in x.items() if v != '' } # Want to be careful with NaNs in the DF here
                              for x in exercise_filters_user_set_snake_keys ]
  print("Processed input json")
  print(exercise_filters_user_set)
  return(exercise_filters_user_set)

@app.route("/regenerate_workout",  methods = ['POST'])
def regenerate_workout():
  # requires "application/json"
  json_from_client = request.get_json()
  exercise_filters_user_set_raw = json_from_client['input_table_dict']
  exercise_filters_user_set = process_input_filters(exercise_filters_user_set_raw)
  # pinned_exercise_ids = json_from_client['pinned_exercise_ids'] if 'pinned_exercise_ids' in json_from_client else []

  pinned_exercise_dict = json_from_client['pinned_input_row_idxs_exercise_ids'] if 'pinned_input_row_idxs_exercise_ids' in json_from_client else {}
  pinned_exercise_ids = pinned_exercise_dict['id'] if 'id' in pinned_exercise_dict else []

  new_workout_df = generate_and_sort_workout(menu_db_query_slct_df, exercise_filters_user_set, pinned_exercise_dict)
  new_workout_table = produce_workout_table_html(new_workout_df, calisthenics_menu_base_url, output_column_names, pinned_exercise_ids)
  return(new_workout_table, 200)

async def push_page(client, page_dict, create_db_result):
  # await asyncio.sleep(3)
  create_page_result = await client.pages.create(
        **{
            'parent': {
              'database_id': create_db_result['id']
            },
            "properties": {k:v for k,v in page_dict.items() if k != 'original_id'}
        }
  )
  # Return mapping of original page to new page in order to append blocks to new page
  return({page_dict['original_id']: create_page_result['id']})
  # await append_blocks_to_page(client, create_page_result['id'], page_id_blocks_mapping[page_dict['original_id']])

async def append_blocks_to_page(client, page_id, blocks_dict_list):
  print(f"Appending {str(len(blocks_dict_list))} blocks to page")
  append_block_result = await client.blocks.children.append(page_id, children=blocks_dict_list)

@app.route("/push_to_notion", methods = ['POST'])
async def push_to_notion():
  # Capture any re-ordering done by the user
  new_workout_ids = request.get_json()
  session['new_workout_ids'] = new_workout_ids

  start_time = time.monotonic()
  print(f'Start asyncio.all_tasks() {asyncio.all_tasks()}')

  if 'oauth_token' not in session:
    return redirect(url_for('login'))
  else:
    notion_pub = AsyncClient(auth=session['oauth_token']['access_token'])
    root_page_id_for_upload = session['root_page_id_for_upload']
    root_page_title_for_upload = session['root_page_title_for_upload']

    # Ignore these when pushing the schema or pushing page data
    types_to_ignore = ['relation']

    # Create a new DB on the server with schema with additional custom Order numeric field not in source Menu DB
    menu_db_schema_for_upload = {k:v for k,v in menu_db_schema['properties'].items() if v['type'] not in types_to_ignore}
    menu_db_schema_for_upload[ORDER_PROPERTY_NAME] = {'name': ORDER_PROPERTY_NAME, 'number': {'format': 'number'}, 'type': 'number'}

    ## Title of new DB
    exercise_categories_str = '-'.join(set([y for x in session['categories'] for y in x]))
    today_str = date.today().strftime('%Y-%m-%d')
    new_db_name = today_str + ' ' + exercise_categories_str

    # Ensure we await on the database schema being pushed *first* before pushing pages
    # Use oauth notion token to push to user's Workspace
    async with notion_pub as client:
      print('Pushing DB Schema')
      create_db_result = await client.databases.create(
        **{
            'parent': {
              'page_id': root_page_id_for_upload,
              'type': 'page_id'
            },
            "title": [
            {
                "type": "text",
                "text": {
                    "content": new_db_name
                }
            }],
            "properties": menu_db_schema_for_upload
      })

      # Prepare data in a format Notion expects
      pages_to_upload = construct_json_rows_for_upload(menu_db_query['results'], list(session['new_workout_ids']), types_to_ignore)

      # Push pages once we have awaited for the schema push
      # Ensure we await all of the Page push tasks in the group to ensure they are done and to collect the results before appending blocks
      pages_task_list = [push_page(client, page_dict, create_db_result) for page_dict in pages_to_upload]
      pages_results = await asyncio.gather(*pages_task_list)
      original_new_page_id_mapping = list_of_dicts_to_dict(pages_results)
      # print(original_new_page_id_mapping)

      # Append Blocks to new pages having awaited for the Pages tasks to complete above
      # Could potentially streamline by adding the append into the same push page function in the case we have 1 page task returned and waiting for a response on the remaining
      if INCLUDE_CHILD_BLOCKS:
        blocks_append_task_list = [
          append_blocks_to_page(
            client,
            original_new_page_id_mapping[page_dict['original_id']], # fetch new page id from mapping
            page_id_blocks_mapping[page_dict['original_id']] # fetch blocks for old page id from mapping
          ) for page_dict in pages_to_upload
        ]
        print("Begin awaiting blocks append")
        await asyncio.gather(*blocks_append_task_list)
        print("Finish awaiting blocks append")

      # # Upload each individual page (row) syncrhonously into the created DB
      # page_create_responses = [] # only for bookkeeping
      # for idx, row_dict in enumerate(row_list_to_upload):
      #   create_page_result = notion_pub.pages.create(
      #     **{
      #         'parent': {
      #           'database_id': create_db_result['id']
      #         },
      #         "properties": {k:v for k,v in row_dict.items() if k != 'original_id'}
      #     }
      #   )
      #   print(f'Pushing {idx+1} of {len(row_list_to_upload)} pages')
      #   page_create_responses.append(create_page_result)

    print(f'Time Taken:{time.monotonic() - start_time}')
    print(f'Pushed {len(pages_to_upload)} pages and their child blocks')

    # Some notion of success. Fix by using try-catch `except APIResponseError as error:` - https://github.com/ramnes/notion-sdk-py
    print(f'End asyncio.all_tasks() {asyncio.all_tasks()}')
    return {"status": "success", "db_url": create_db_result['url']}, 200

    # num_pages_created_successfully = len([x['created_time'] is not None for x in page_create_responses]) # Unsure what this returns if fails
    # if num_pages_created_successfully == len(row_list_to_upload):
    #   return {"status": "success", "db_url": create_db_result['url']}, 200
    # else:
    #   return {"status": "failed"}, 500

@app.route("/option_filter_frequency", methods = ['POST'])
def option_filter_frequency():
  exercise_filters_user_set_raw = request.get_json()
  exercise_filters_user_set = process_input_filters([exercise_filters_user_set_raw])

  exercise_sub_population = filter_groups(menu_db_query_slct_df, exercise_filters_user_set[0])
  return({'total_num_exercises': len(exercise_sub_population)}, 200)

# Oauth
@app.route("/login")
def login():
    notion_oauth = OAuth2Session(CLIENT_ID)
    authorization_url, state = notion_oauth.authorization_url(authorization_base_url)
    # print(authorization_url)

    # State is used to prevent CSRF, keep this for later.
    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route("/oauth2_callback")
def oauth2_callback():
    notion_oauth = OAuth2Session(CLIENT_ID, state=session['oauth_state'])
    # print(request.url)

    # From oauth2_session.py
    token = notion_oauth.fetch_token(token_url,
                                      # include_client_id=True,
                                      method='POST',
                                      authorization_response=request.url,
                                      # code=dict(urldecode(request.url))['http://localhost:5000/oauth2_callback?code'],
                                      # auth = (CLIENT_ID, CLIENT_SECRET),
                                      client_secret=CLIENT_SECRET,
                                      # Including this header breaks the call
                                      # headers = {
                                      #   'Content-Type': 'application/json'
                                      # },
                                      kwargs={
                                        'grant_type': 'authorization_code'
                                      })
    # print(token)
    session['oauth_token'] = token
    # return(jsonify(token))

    notion_pub = Client(auth=session['oauth_token']['access_token'])
    possible_pages_for_upload = notion_pub.search(filter={'value':'page', 'property':'object'})['results']
    root_page_metadata_for_upload = [x for x in possible_pages_for_upload if x['parent']['type'] == 'workspace'][0]
    root_page_id_for_upload = root_page_metadata_for_upload['id']
    root_page_title_for_upload = root_page_metadata_for_upload['properties']['title']['title'][0]['plain_text']
    root_page_url_for_upload = root_page_metadata_for_upload['url']

    session['root_page_id_for_upload'] = root_page_id_for_upload
    session['root_page_title_for_upload'] = root_page_title_for_upload
    session['root_page_url_for_upload'] = root_page_url_for_upload

    return redirect(url_for('default_workout'))
