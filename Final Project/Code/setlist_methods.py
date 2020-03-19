#import musicbrainzngs
import datetime
import requests
import time
import networkx as nx
from dateutil.relativedelta import relativedelta
import plotly.graph_objects as go
import numpy as np

START_DATE = datetime.datetime.strptime('2015-01-01', '%Y-%m-%d')
END_DATE = datetime.datetime.today()

def get_setlist_events(seed_id, SETLIST_API_KEY, seed_type="artist", verbose=True, limit=100, n_tries=5):
  # need to do this first pull outside of loop to get total # events
  page = 1
  if verbose:
  	print("fetching page number %d.." % page)
  request = 'https://api.setlist.fm/rest/1.0/{0}/{1}/setlists?p={2}'.format(seed_type, seed_id, page)
  headers = {'Accept': 'application/json', 'x-api-key': SETLIST_API_KEY}
  results = requests.get(request, headers=headers)
  json_results = results.json()
  # Avoid errors from making too many requests in a row
  tried = 1
  while ('total' not in json_results.keys()) and (tried < n_tries):
    time.sleep(1)
    print("Trying again...")
    results = requests.get(request, headers=headers)
    json_results = results.json()
    tried += 1
  total_events = json_results['total']
  per_page = json_results['itemsPerPage']
  events = json_results['setlist']
  max_events = min(total_events, limit)
  if verbose:
    print("Will fetch {0} out of {1} events".format(max_events, total_events))
  while len(events) < max_events:
    page += 1
    if verbose:
    	print("fetching page number %d.." % page)
    time.sleep(0.075) # avoid hitting API's request/time limit
    request = 'https://api.setlist.fm/rest/1.0/{0}/{1}/setlists?p={2}'.format(seed_type, seed_id, page)
    results = requests.get(request, headers=headers)
    json_results = results.json()
    tried = 1
    while ('setlist' not in json_results.keys()) and (tried < n_tries):
      time.sleep(1)
      print("Trying again...")
      results = requests.get(request, headers=headers)
      json_results = results.json()
    events += json_results['setlist']
    if verbose:
    	print("Fetched {} events".format(len(events)))
  if verbose:
  	print("")
  	print("\n%d events on  %d pages" % (len(events), page))
  return events

def add_sl_events_to_bipartite_graph(sl_events, G, start_date=START_DATE, end_date=END_DATE):
  for event in sl_events:
    event_date = datetime.datetime.strptime(event['eventDate'], '%d-%m-%Y')
    if (event_date >= start_date) & (event_date <= end_date):
      place_info = event['venue']
      G.add_node(place_info['id'], name=place_info['name'], node_type="Venue")
      artist_info = event['artist']
      G.add_node(artist_info['mbid'], name=artist_info['name'], \
                     node_type="Artist")
      G.add_edge(artist_info['mbid'], place_info['id'])
