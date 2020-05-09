import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import musicbrainzngs
import datetime
import requests
import time
import json

def not_none(x, y=None):
    if x is None:
        return y
    return x

#####################

class Artist:
  def __init__(self):
    self.mbid = None
    self.name = None

  def __eq__(self, other):
    if isinstance(other, Artist):
      return (self.mbid == other.mbid) and (self.name == other.name)
    return False

  def load_from_mb_artist(self, mb_artist_info):
    self.mbid = mb_artist_info['id']
    self.name = mb_artist_info['name']

  def load_from_sl_event(self, sl_event):
    self.mbid = sl_event['artist']['mbid']
    self.name = sl_event['artist']['name']

  def from_dict(self, artist_dict):
    self.mbid = artist_dict['mbid']
    self.name = artist_dict['name']

  def to_dict(self):
    return dict(mbid=self.mbid, name=self.name)

  def to_tuple(self):
    return (self.mbid, self.name)

  def flatten(self):
    return dict(artist_mbid=self.mbid, artist_name=self.name)

  # Assumes fields not empty
  def add_to_bigraph(self, G):
    G.add_node(self.mbid, name=self.name, node_type="Artist")
    return self.mbid

###################

class Venue:
  def __init__(self, venue_dict=None):
    if venue_dict is None:
      self.id = dict(mbid=None, slid=None)
      self.name = dict(mbname=None, slname=None)
      self.city = dict(name=None, coords=(None, None))
      self.coords = (None, None)
    else:
      self.id = venue_dict['id']
      self.name = venue_dict['name']
      self.city = venue_dict['city']
      self.coords = venue_dict['coords']

  def __repr__(self):
    return "Venue({})".format(self.to_dict())

  def __eq__(self, other):
    if isinstance(other, Venue):
      return self.to_dict() == other.to_dict()
    return False

  def load_from_mb_event(self, mb_event):
    if 'place-relation-list' in mb_event.keys():
          for place_rel in mb_event['place-relation-list']:
              if place_rel['type'] == 'held at':
                place_info = place_rel['place']
          self.id['mbid'] = place_info['id']
          self.name['mbname'] = place_info['name']
          if 'coordinates' in place_info.keys():
            self.coords = (float(place_info['coordinates']['latitude']),\
              float(place_info['coordinates']['longitude']))

  def load_from_sl_event(self, sl_event):
    self.id['slid'] = sl_event['venue']['id']
    self.name['slname'] = sl_event['venue']['name']
    self.city['name'] = sl_event['venue']['city']['name']
    # Most Setlist.fm venues should have city coords, but a few exceptions
    if bool(sl_event['venue']['city']['coords']):
      self.city['coords'] = (sl_event['venue']['city']['coords']['lat'],\
        sl_event['venue']['city']['coords']['long'])

  def from_dict(self, venue_dict):
    self.id = venue_dict['id']
    self.name = venue_dict['name']
    self.city = venue_dict['city']
    self.coords = venue_dict['coords']

  def to_dict(self):
    new_dict = dict(id=self.id, name=self.name, city=self.city, coords=self.coords)
    return new_dict

  def flatten(self):
    new_dict = dict(venue_mbid=self.id['mbid'], venue_slid=self.id['slid'], \
      venue_mbname=self.name['mbname'], venue_slname=self.name['slname'], \
      city_name=self.city['name'], city_lat=self.city['coords'][0], \
      city_long=self.city['coords'][1], \
      venue_lat=self.coords[0], venue_long=self.coords[1])
    return new_dict

  def is_empty(self):
    return (self.id['mbid'] is None) and (self.id['slid'] is None)

  # Updates this venue object
  def merge_with(self, other):
    self.id['mbid'] = not_none(self.id['mbid'], other.id['mbid'])
    self.id['slid'] = not_none(self.id['slid'], other.id['slid'])
    self.name['mbname'] = not_none(self.name['mbname'], other.name['mbname'])
    self.name['slname'] = not_none(self.name['slname'], other.name['slname'])
    self.city['name'] = not_none(self.city['name'], other.city['name'])
    self.city['coords'] = not_none(self.city['coords'], other.city['coords'])
    self.coords = not_none(self.coords, other.coords)

  # Assumes venue not empty...
  def add_to_bigraph(self, G):
    venue_id = not_none(self.id['mbid'], self.id['slid'])
    venue_name = not_none(self.name['mbname'], self.name['slname'])
    G.add_node(venue_id, name=venue_name, node_type='Venue')
    return venue_id

####################

class Event:
  def __init__(self):
    self.id = dict(mbid=None, slid=None)
    self.time = None
    self.type = None
    self.artists = []
    self.venue = Venue()
    self.url = dict(mburl=None, slurl=None)

  def load_from_mb_event(self, mb_event):
    self.id['mbid'] = mb_event['id']
    if 'life-span' in mb_event.keys():
      for fmt in ('%Y-%m-%d', '%Y-%m', '%Y'):
          try:
            self.time = datetime.datetime.strptime(mb_event['life-span']['begin'], fmt).date()
          except ValueError:
            pass
    if 'type' in mb_event.keys():
      self.type = mb_event['type']
    if 'artist-relation-list' in mb_event.keys():
      for artist in mb_event['artist-relation-list']:
        artist_info = artist['artist']
        new_artist = Artist()
        new_artist.load_from_mb_artist(artist_info)
        self.artists.append(new_artist)
    self.venue.load_from_mb_event(mb_event)
    self.url['mburl'] = 'https://musicbrainz.org/event/'+mb_event['id']

  def load_from_sl_event(self, sl_event):
    self.id['slid'] = sl_event['id']
    self.time = datetime.datetime.strptime(sl_event['eventDate'], '%d-%m-%Y').date()
    new_artist = Artist()
    new_artist.load_from_sl_event(sl_event)
    self.artists.append(new_artist)
    self.venue.load_from_sl_event(sl_event)
    self.url['slurl'] = sl_event['url']

  def from_dict(self, event_dict):
    self.id = event_dict['id']
    self.time = event_dict['time']
    self.type = event_dict['type']
    for artist in event_dict['artists']:
      new_artist = Artist()
      self.artists.append(new_artist.from_dict(artist))
    self.venue.from_dict(event_dict['venue'])
    self.url = event_dict['url']

  def set_venue(self, new_venue):
    if isinstance(new_venue, Venue):
      self.venue = new_venue

  def to_dict(self):
    new_dict = dict(id=self.id,\
      time=self.time, type=self.type, \
      artists=[artist.to_dict() for artist in self.artists], venue=self.venue.to_dict(),\
      url=self.url)
    return new_dict

  # Convert to form that should be easy to then convert to DataFrame
  def flatten(self):
    flat_event = dict(event_mbid=self.id['mbid'], event_slid=self.id['slid'], \
      time=self.time, event_type=self.type, event_mburl=self.url['mburl'],\
      event_slurl=self.url['slurl'])
    flat_venue = self.venue.flatten()
    flat_events = []
    for artist in self.artists:
      flat_artist = artist.flatten()
      flat_artist_event = {**flat_event, **flat_venue, **flat_artist}
      flat_events.append(flat_artist_event)
    return flat_events

  def same_event(self, other):
    if (self.id['mbid'] == other.id['mbid']) or (self.id['slid'] == other.id['slid']):
      return True #definitely same event
    else: 
      these_artists = set([a.to_tuple() for a in self.artists])
      those_artists = set([a.to_tuple() for a in other.artists])
      if (self.time == other.time) and (these_artists.issubset(those_artists) or \
        those_artists.issubset(these_artists)):
        return True #probably the same event (assume artists only have 1 event per day)
      else:
        return False

  # Updates this event object
  def merge_with(self, other):
    #if self.same_event(other):
      self.id['mbid'] = not_none(self.id['mbid'], other.id['mbid'])
      self.id['slid'] = not_none(self.id['slid'], other.id['slid'])
      self.type = not_none(self.type, other.type)
      self.url['mburl'] = not_none(self.url['mburl'], other.url['mburl'])
      self.url['slurl'] = not_none(self.url['slurl'], other.url['slurl'])
      if len(self.artists) < len(other.artists):
        self.artists = other.artists
      self.venue.merge_with(other.venue)

  def valid_date(self, start_date, end_date):
    if (self.time is None):
      return False
    else:
      return (self.time >= start_date) & (self.time <= end_date) 

  def add_to_bigraph(self, G):
    if not self.venue.is_empty():
      venue_node_id = self.venue.add_to_bigraph(G)
      if len(self.artists) > 0:
        for artist in self.artists:
          artist_node_id = artist.add_to_bigraph(G)
          G.add_edge(artist_node_id, venue_node_id)

#####################
# For now assume one-to-one mapping (prob a faulty assumption...)
class VenueMapper:
  def __init__(self):
    self.venue_mapping = {}

  #takes form id: dictionary rep of Venue object
  def load_json(self, filename):
    with open(filename, 'r') as f:
      loaded_dict = json.load(f)
    for key, value in loaded_dict.items():
      self.venue_mapping[key] = Venue(value)

  def dump_json(self, filename):
    venue_dump = {}
    for venue_id, venue in self.venue_mapping.items():
      venue_dump[venue_id] = venue.to_dict()
    if bool(venue_dump):
      with open(filename, 'w') as f:
        json.dump(venue_dump, f)

  def add_venue(self, map_id, venue):
      self.venue_mapping[map_id] = venue

  def has_id(self, check_id):
    return(check_id in self.venue_mapping)

  def get_venue(self, query_id):
    return self.venue_mapping[query_id]

#####################

class SetlistAPIError(Exception):
    pass

class SetlistNotFoundError(Exception):
  pass

#####################

class SetlistPuller:
  def __init__(self, api_key):
    self.api_key = api_key

  def pull_page(self, seed_id, seed_type, page):
    request = 'https://api.setlist.fm/rest/1.0/{0}/{1}/setlists?p={2}'.format(\
      seed_type, seed_id, page)
    headers = {'Accept': 'application/json', 'x-api-key': self.api_key}
    results = requests.get(request, headers=headers)
    json_results = results.json()
    if 'code' in json_results:
      if json_results['code'] == 404:
        raise SetlistNotFoundError
    return json_results

  def pull_until_success(self, seed_id, seed_type, page, check_key, limit=10):
    try:
      page_results = self.pull_page(seed_id, seed_type, page) 
      attempts = 1
      while (check_key not in page_results.keys()) and (attempts < limit):
          time.sleep(1)
          page_results = self.pull_page(seed_id, seed_type, page)
          attempts += 1
      if check_key in page_results.keys():
        return page_results
    except SetlistNotFoundError:
      raise
    raise SetlistAPIError("Too many attempts")

  def pull_events(self, seed_id, seed_type, limit=5):
    page = 1
    try:
      page_results = self.pull_until_success(seed_id, seed_type, page, 'total')
      total_events = page_results['total']
      per_page = page_results['itemsPerPage']
      events = page_results['setlist']
      while (page < limit) and (len(events) < total_events):
        page += 1
        page_results = self.pull_until_success(seed_id, seed_type, page, 'setlist')
        events += page_results['setlist']
      return events
    except SetlistAPIError:
      print('Could not pull Setlist.fm events')
      raise
    except SetlistNotFoundError:
      print('No Setlist.fm events found')
      return []

#####################

class MusicBrainzPuller:
  def __init__(self, app, version):
    musicbrainzngs.set_useragent(app=app, version=version)

  def pull_page(self, mbid, seed_type, limit, offset):
    args = dict(includes=["event-rels", "place-rels", "artist-rels"], \
      limit=limit, offset=offset)
    if seed_type=='venue':
      args['place']=mbid
    else:
      args[seed_type]=mbid
    result = musicbrainzngs.browse_events(**args)
    return result

  def pull_events(self, mbid, seed_type, limit=100, offset=0):
    events = []
    page = 1
    result = self.pull_page(mbid, seed_type, limit, offset)
    events_list = result['event-list']
    events += events_list
    while len(events_list) >= limit: # last page should have less than the limit
      offset += limit
      page += 1
      result = self.pull_page(mbid, seed_type, limit, offset)
      events_list = result['event-list']
      events += events_list
    return events

#####################

def merge_event_lists(events1, events2, venue_mapper):
  """
  Combine two event lists, merging Event objects that describe same event

  Keyword arguments:
  events1, events2 -- lists of Event objects to merge
  venue_mapper -- instance of class VenueMapper to update with any new venue mappings found
  """
  if len(events1) == 0:
    return events2
  elif len(events2) == 0:
    return events1
  else:
    filtered_events1 = []
    merged_count = 0
    for ev1 in events1:
      found_dupe = False
      for ev2 in events2:
        if ev2.same_event(ev1):
          found_dupe = True
          ev2.merge_with(ev1) # update ev2 in place with values from ev1
          merged_count += 1
          v2_mbid = ev2.venue.id['mbid']
          v2_slid = ev2.venue.id['slid']
          # Existing venue mappings take priority
          if (not venue_mapper.has_id(v2_mbid)) or (not venue_mapper.has_id(v2_slid)):
            venue_mapper.add_venue(ev2.venue.id['mbid'], ev2.venue)
            venue_mapper.add_venue(ev2.venue.id['slid'], ev2.venue)
      if not found_dupe:
        v1_id = not_none(ev1.venue.id['mbid'], ev1.venue.id['slid'])
        filtered_events1.append(ev1)
    print("Merged {} events".format(merged_count))
    return filtered_events1 + events2

def get_mb_and_sl_events(mbid, mb_event_puller, sl_event_puller, venue_mapper, \
  start_date, end_date, seed_type="artist", slid=None, sl_page_limit=5):
  """
  Pull entity's events from MusicBrainz and Setlist.fm and apply venue mappings when applicable. 
  Attempt to merge events that occur in both, return list of Event objects and summary text

  Keyword arguments:
  mbid -- the MusicBrainz ID of the artist or venue for which to pull events
  mb_event_puller -- instance of class MusicBrainzPuller
  sl_event_puller -- instance of class SetlistPuller
  venue_mapper -- instance of class VenueMapper
  start_date, end_date -- range of dates for events to return (type datetime.date)
  seed_type -- type of entity to pull events for ("artist" or "venue", default "artist")
  slid -- Setlist.fm ID of the venue to pull events for, if seed_type is "venue" (default None)
  sl_page_limit -- maximum number of results pages to pull from Setlist.fm (default 5)
  """
  valid_mb_events = []
  valid_sl_events = []
  message = ""
  if seed_type=='artist':
    sl_seed_id = mbid
  else:
    sl_seed_id = slid # only use Setlist.fm ID when pulling venue events
  if mbid:
    mb_events = mb_event_puller.pull_events(mbid=mbid, seed_type=seed_type)
    for mb_event in mb_events:
      event = Event()
      event.load_from_mb_event(mb_event)
      if event.valid_date(start_date, end_date):
        if (len(event.artists) > 0) and not event.venue.is_empty():
          if venue_mapper.has_id(event.venue.id['mbid']):
            event.set_venue(venue_mapper.get_venue(event.venue.id['mbid']))
          valid_mb_events.append(event)
    message = "Retrieved {} MusicBrainz events between {} and {}. ".format(\
      len(valid_mb_events), start_date, end_date)

  if sl_seed_id: 
    try:
      sl_events = sl_event_puller.pull_events(\
        seed_id=sl_seed_id, seed_type=seed_type, limit=sl_page_limit)
      for sl_event in sl_events:
        event = Event()
        event.load_from_sl_event(sl_event)
        if event.valid_date(start_date, end_date):
          if venue_mapper.has_id(event.venue.id['slid']):
            event.set_venue(venue_mapper.get_venue(event.venue.id['slid']))
          valid_sl_events.append(event)
      message = message + "Retrieved {} Setlist events between {} and {},".format(\
        len(valid_sl_events), start_date, end_date)
      message = message + " limited to the {} most recent. ".format(sl_page_limit*20)
    except SetlistAPIError:
      message = message + "Setlist daily query limit reached, so no events pulled. "
      print("Issue pulling Setlist events - will use MusicBrainz only")
      pass
  print("Retrieved {} MB events, {} SL events".format(len(valid_mb_events), len(valid_sl_events)))
  valid_events = merge_event_lists(valid_mb_events, valid_sl_events, venue_mapper)
  return valid_events, message

def get_basic_artist_rec_from_df(df, query_id, n_recs=10):
  """
  Generate DataFrame of artists in the event dataset that have performed at the most (unique) venues

  Keyword arguments:
  df -- pandas DataFrame of events for venues at which query artist has performed; assume non-empty
  query_id -- MBID of query artist (ensures that query artist not in list of recommendations)
  n_recs -- number of recommended artists to return (default 10)

  """
  df['venue_id'] = list(zip(df.venue_mbid, df.venue_slid))
  df = df[df['artist_mbid'] != query_id]
  grouped_df = df.groupby(['artist_mbid', 'artist_name']).agg({'venue_id':'nunique'})
  top_artists = grouped_df.sort_values(by=['venue_id'], ascending=False).head(n=n_recs)
  top_artists = top_artists.reset_index()
  top_artists = top_artists.rename(columns={'artist_mbid':'id', 
    'artist_name':'Artist', 
    'venue_id':'Shared Venues'})
  cols_to_return = ['id', 'Artist', 'Shared Venues']
  top_artists = top_artists[cols_to_return]
  return top_artists

def get_events_list(query_artist_events, mb_event_puller, sl_event_puller, venue_mapper, \
  start_date, end_date, sl_page_limit):
  """
  For each event in input list, pull all events held at venue; return list of events in standardized
  (flattened) form

  Keyword arguments:
  query_artist_events -- list of dictionary representations of events, expected to each have keys 
  needed to convert to Event objects
  mb_event_puller -- instance of MusicBrainzPuller class
  sl_event_puller -- instance of class SetlistPuller
  venue_mapper -- instance of class VenueMapper
  start_date, end_date -- range of dates for events to return (type datetime.date)
  sl_page_limit -- maximum number of results pages to pull from Setlist.fm
  """
  venue_event_dict = {}
  all_events = []
  for event_dict in query_artist_events:
    event = Event()
    event.from_dict(event_dict)
    venue_id = not_none(event.venue.id['mbid'], event.venue.id['slid'])
    if venue_mapper.has_id(venue_id):
      event.set_venue(venue_mapper.get_venue(venue_id))
    
    venue_mbid = event.venue.id['mbid']
    venue_slid = event.venue.id['slid']

    new_events = []
    new_key = (venue_mbid, venue_slid)
    if new_key not in venue_event_dict:
      new_events, message = get_mb_and_sl_events(venue_mbid, \
        mb_event_puller, sl_event_puller, venue_mapper, \
        start_date, end_date, seed_type="venue", slid=venue_slid, \
        sl_page_limit=sl_page_limit)
      venue_event_dict[new_key] = new_events
      flattened_events = [x.flatten() for x in new_events]
      all_events += flattened_events
  all_events = [y for x in all_events for y in x]
  return all_events


def generate_artist_events_map(query_artist_events, query_mbid):
  """
  Create geographical plot of query artist events with lat/long data,
  return plot object, number of events plotted, and text summarizing events not
  plotted

  Keyword arguments:
  query_artist_events -- list of Event objects
  query_mbid -- MBID of artist whose events we want to plot
  """
  std_events = [event.flatten() for event in query_artist_events]
  std_events =  [y for x in std_events for y in x if \
    y['artist_mbid'] == query_mbid]

  query_artist_name = std_events[0]['artist_name']
  mappable_events = [event for event in std_events if \
    ('venue_lat' in event) or ('city_lat' in event)]
  non_mappable_events = [event for event in std_events if \
    event not in mappable_events]
  
  non_mappable_text = ["{artist} @ {venue} ({date})".format(date=str(x['time']), \
      artist=x['artist_name'], venue=not_none(x['venue_mbname'], x['venue_slname'])) \
      for x in non_mappable_events]
  non_mappable_text = "; ".join(non_mappable_text)

  for event in mappable_events:
      event['url'] = not_none(event['event_slurl'], event['event_mburl'])
      if event['venue_lat']: #not None
          event['venue_name'] = event['venue_mbname']
          event['coord_type'] = 'venue'
          event['lat'] = event['venue_lat']
          event['lon'] = event['venue_long']
      else:
          event['venue_name'] = event['venue_slname']
          event['coord_type'] = event['city_name']
          event['lat'] = event['city_lat']
          event['lon'] = event['city_long']

  if len(mappable_events) > 0:
      df = pd.DataFrame(mappable_events)
      df['text'] = df['artist_name'] + ' @ ' + df['venue_name'] + \
          ' (' + df['time'].apply(lambda x: str(x)) + ')'

      df['venue_mbid'] = df['venue_mbid'].fillna('')
      df['venue_slid'] = df['venue_slid'].fillna('')
      df['venue_id'] = list(zip(df.venue_mbid, df.venue_slid))
      df_grouped = df.groupby(['venue_name', 'venue_id', 'lat', 'lon', 'coord_type'])
      events_by_venue_text = df_grouped['text'].agg(lambda x:'<br>'.join(x))
      events_by_venue = events_by_venue_text.reset_index()
      events_by_venue['text'] = events_by_venue['text'] + '<br>Mapped using '+ \
        events_by_venue['coord_type'] + ' coordinates.' 
        #LightSeaGreen
      fig = go.Figure(data=go.Scattergeo(
          lon = events_by_venue['lon'],
          lat = events_by_venue['lat'],
          text = events_by_venue['text'],
          hoverinfo = 'text',
          customdata = events_by_venue[['venue_name', 'venue_id']].apply(tuple, axis=1),
          mode = 'markers',
          marker = dict(color="LightSeaGreen", size=8, opacity=0.6, symbol='star',
            line=dict(width=2, color='DarkSlateGrey'))
          ), 
        layout=go.Layout(autosize=True, margin=go.layout.Margin(l=0, r=0, t=0, b=0),
          showlegend=False))
      fig.update_geos(showcountries=True)
      return fig, len(mappable_events), non_mappable_text
  else:
      return default_map_figure, 0, non_mappable_text

def get_more_artist_info(mbid):
  out_dict = dict(area=None, life_span=None, top_tags=[])
  try:
    mb_info = musicbrainzngs.get_artist_by_id(mbid, includes=['tags'])
    mb_info = mb_info['artist']
    if 'area' in mb_info:
      out_dict['area'] = mb_info['area']['name']
    if 'life-span' in mb_info:
      life_span = mb_info['life-span']
      begin = ''
      end = ''
      if 'begin' in life_span:
        begin = life_span['begin']
      if 'end' in life_span:
        end = life_span['end']
      out_dict['life_span'] = '{} - {}'.format(begin, end)
    if 'tag-list' in mb_info:
      tag_dicts = mb_info['tag-list']
      sorted_tag_list = sorted(tag_dicts, key = lambda i: -int(i['count'])) 
      sorted_tag_list = [x['name'] for x in sorted_tag_list] 
      out_dict['top_tags'] = sorted_tag_list[:3]
  except requests.HTTPError as err:
    print("HTTPError: {0}".format(err))
    pass
  except musicbrainzngs.ResponseError as err:
    print("ResponseError: {0}".format(err))
    pass
  return out_dict
