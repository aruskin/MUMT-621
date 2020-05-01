import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import musicbrainzngs
import datetime
import requests
import time
import json

def try_parsing_mb_date(text):
    for fmt in ('%Y-%m-%d', '%Y-%m', '%Y'):
        try:
            return datetime.datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError('no valid date format found')

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
          self.id['key_id'] = 'mbid'
          self.name['mbname'] = place_info['name']
          if 'coordinates' in place_info.keys():
            self.coords = (float(place_info['coordinates']['latitude']),\
              float(place_info['coordinates']['longitude']))

  def load_from_sl_event(self, sl_event):
    self.id['slid'] = sl_event['venue']['id']
    self.id['key_id'] = 'slid'
    self.name['slname'] = sl_event['venue']['name']
    self.city['name'] = sl_event['venue']['city']['name']
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
      city_name=self.city['name'], city_lat=self.city['coords'][0], city_long=self.city['coords'][1],\
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
    self.name = dict(mbname=None, slname=None)
    self.time = None
    self.type = None
    self.artists = []
    self.venue = Venue()

  def load_from_mb_event(self, mb_event):
    self.id['mbid'] = mb_event['id']
    self.name['mbname'] = mb_event['name']
    if 'life-span' in mb_event.keys():
      for fmt in ('%Y-%m-%d', '%Y-%m', '%Y'):
          try:
            self.time = datetime.datetime.strptime(mb_event['life-span']['begin'], fmt)
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

  def load_from_sl_event(self, sl_event):
    self.id['slid'] = sl_event['id']
    self.time = datetime.datetime.strptime(sl_event['eventDate'], '%d-%m-%Y')
    new_artist = Artist()
    new_artist.load_from_sl_event(sl_event)
    self.artists.append(new_artist)
    self.venue.load_from_sl_event(sl_event)

  def set_venue(self, new_venue):
    if isinstance(new_venue, Venue):
      self.venue = new_venue

  def to_dict(self):
    new_dict = dict(id=self.id, name=self.name, time=self.time, type=self.type, \
      artists=[artist.to_dict() for artist in self.artists], venue=self.venue.to_dict())
    return new_dict

  # Convert to form that should be easy to then convert to DataFrame
  def flatten(self):
    flat_event = dict(event_mbid=self.id['mbid'], event_slid=self.id['slid'], \
      event_mbname=self.name['mbname'], event_slname=self.name['slname'], \
      time=self.time, event_type=self.type)
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
      if (self.time == other.time) and (these_artists.issubset(those_artists) or those_artists.issubset(these_artists)):
        return True #probably the same event (assume artists only have 1 event per day)
      else:
        return False

  # Updates this event object
  def merge_with(self, other):
    #if self.same_event(other):
      self.id['mbid'] = not_none(self.id['mbid'], other.id['mbid'])
      self.id['slid'] = not_none(self.id['slid'], other.id['slid'])
      self.name['mbname'] = not_none(self.name['mbname'], other.name['mbname'])
      self.name['slname'] = not_none(self.name['slname'], other.name['slname'])
      self.type = not_none(self.type, other.type)
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
    for key, value in self.venue_mapping.items():
      venue_dump[key] = value.to_dict()
    if bool(venue_dump):
      with open(filename, 'w') as f:
        json.dump(venue_dump, filename)

  def add_venue(self, map_id, venue):
      self.venue_mapping[map_id] = venue

  def has_id(self, check_id):
    return(check_id in self.venue_mapping)

  def get_venue(self, query_id):
    return self.venue_mapping[query_id]

#####################

class SetlistAPIError(Exception):
    pass

#####################

class SetlistPuller:
  def __init__(self, api_key):
    self.api_key = api_key

  def pull_page(self, seed_id, seed_type, page):
    request = 'https://api.setlist.fm/rest/1.0/{0}/{1}/setlists?p={2}'.format(seed_type, seed_id, page)
    headers = {'Accept': 'application/json', 'x-api-key': self.api_key}
    results = requests.get(request, headers=headers)
    json_results = results.json()
    return json_results

  def pull_until_success(self, seed_id, seed_type, page, check_key, limit=10):
    page_results = self.pull_page(seed_id, seed_type, page)
    attempts = 1
    while (check_key not in page_results.keys()) and (attempts < limit):
      time.sleep(1)
      page_results = self.pull_page(seed_id, seed_type, page)
      attempts += 1
    if check_key in page_results.keys():
      return page_results
    raise SetlistAPIError

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
          ev2.merge_with(ev1)
          merged_count += 1
          venue_mapper.add_venue(ev2.venue.id['mbid'], ev2.venue)
          venue_mapper.add_venue(ev2.venue.id['slid'], ev2.venue)
      if not found_dupe:
        filtered_events1.append(ev1)
    print("Merged {} events".format(merged_count))
    return filtered_events1 + events2

def get_mb_and_sl_events(mbid, mb_event_puller, sl_event_puller, venue_mapper, start_date, end_date, seed_type="artist", slid=None, sl_page_limit=5):
  valid_mb_events = []
  valid_sl_events = []

  if seed_type=='artist':
    sl_seed_id = mbid
  else:
    sl_seed_id = slid
  if mbid:
    mb_events = mb_event_puller.pull_events(mbid=mbid, seed_type=seed_type)
    for mb_event in mb_events:
      event = Event()
      event.load_from_mb_event(mb_event)
      if event.valid_date(start_date, end_date):
        if (len(event.artists) > 0) and not event.venue.is_empty():
          valid_mb_events.append(event)

  if sl_seed_id: 
    try:
      sl_events = sl_event_puller.pull_events(seed_id=sl_seed_id, seed_type=seed_type, limit=sl_page_limit)
      for sl_event in sl_events:
        event = Event()
        event.load_from_sl_event(sl_event)
        if event.valid_date(start_date, end_date):
          valid_sl_events.append(event)
    except SetlistAPIError:
      print("Issue pulling Setlist events - will use MusicBrainz only")
      pass
  print("{} MB events, {} SL events".format(len(valid_mb_events), len(valid_sl_events)))
  valid_events = merge_event_lists(valid_mb_events, valid_sl_events, venue_mapper)
  return valid_events

def get_mb_artist_area(mbid):
  mb_info = musicbrainzngs.get_artist_by_id(mbid)
  mb_info = mb_info['artist']
  if 'area' in mb_info.keys():
    area = mb_info['area']['name']
  else:
    area = 'N/A'
  return area

def get_basic_artist_rec_from_df(df, query_id, with_geo=True, n_recs=10):
  df['venue_id'] = list(zip(df.venue_mbid, df.venue_slid))
  df = df[df['artist_mbid'] != query_id]
  grouped_df = df.groupby(['artist_mbid', 'artist_name']).agg({'venue_id':'nunique'})
  top_artists = grouped_df.sort_values(by=['venue_id'], ascending=False).head(n=n_recs)
  top_artists = top_artists.reset_index()
  top_artists = top_artists.rename(columns={'artist_name':'Artist', 'venue_id':'Shared Venues'})
  if with_geo:
    top_artists['Origin'] = top_artists['artist_mbid'].apply(get_mb_artist_area)
    cols_to_return = ['Artist', 'Origin', 'Shared Venues']
  else:
    cols_to_return = ['Artist', 'Shared Venues']
  top_artists = top_artists[cols_to_return]
  return top_artists

#####################

# Return list of artists with the most overlapping venues as query artist
# (Doesn't take into account how often they've played at these venues,
# whether they've shared bill with query artist, etc.)
# Assume bipartite graph of artist-venue data
def get_basic_artist_rec_from_bigraph(bi_G, query_id, n_recs=10):
  venues, artists = nx.bipartite.sets(bi_G)
  venue_degrees, artist_degrees = nx.bipartite.degrees(bi_G, artists)
  artists_ranked = [(k, v) for k, v in sorted(artist_degrees, key=lambda item: item[1], reverse=True) \
                    if k != query_id]
  num_venues = len(venues)
  outlist = artists_ranked[:n_recs]
  artists_and_info = []
  for mbid, deg in outlist:
    artist_info = {'name':'', 'area':'', 'shared_venues': deg}
    mb_info = musicbrainzngs.get_artist_by_id(mbid)
    mb_info = mb_info['artist']
    artist_info['name'] = mb_info['name']
    if 'area' in mb_info.keys():
      artist_info['area'] = mb_info['area']['name']
    artists_and_info += [artist_info]
  #outlist = [(bi_G.nodes[x]['name'], y) for x, y in outlist]
  df = pd.DataFrame(artists_and_info)
  df = df.rename(columns={'name':'Artist', 'shared_venues':'Shared Venues', 'area':'Origin'})
  return df


def plot_network(G, mbid, bipartite=False):
  seed_artist = G.nodes[mbid]['name']

  # Some things should prob differ depending on type of graph, but still figuring that out
  if bipartite:
    plot_title = "<br>Artist-venue graph for {}".format(seed_artist)  
  else:
    plot_title = "<br>Artist-event-venue graph for {}".format(seed_artist)  
  
  pos = nx.layout.spring_layout(G)

  for node in G.nodes:
    G.nodes[node]['pos'] = list(pos[node])

  edge_x = []
  edge_y = []
  for edge in G.edges():
      x0, y0 = G.nodes[edge[0]]['pos']
      x1, y1 = G.nodes[edge[1]]['pos']
      edge_x.append(x0)
      edge_x.append(x1)
      edge_x.append(None)
      edge_y.append(y0)
      edge_y.append(y1)
      edge_y.append(None)

  edge_trace = go.Scatter(
      x=edge_x, y=edge_y,
      line=dict(width=0.5, color='#888'),
      hoverinfo='none',
      mode='lines')

  node_x = []
  node_y = []
  node_text = []
  node_types = []
  bipartite_node_coloring = []
  for node in G.nodes():
      x, y = G.nodes[node]['pos']
      node_x.append(x)
      node_y.append(y)
      # Every node should have some human readable info associated with it
      text = G.nodes[node]['name'] + "<br>Type: {}".format(G.nodes[node]['node_type'])
      if 'date' in G.nodes[node].keys():
          text = text + "<br>Date: {}".format(G.nodes[node]['date'])
      if node == mbid:
        node_types.append('Seed')
        bipartite_node_coloring.append(G.degree(node))
      else:
        node_types.append(G.nodes[node]['node_type'])
        if bipartite:
          if G.nodes[node]['node_type'] == "Artist":
            node_degree = G.degree(node)
            bipartite_node_coloring.append(node_degree)
            text = text + "<br>Shared venues: {}".format(node_degree)
          else:
            bipartite_node_coloring.append(0)
      node_text.append(text)
  
  # Set node colors based on type (Seed, Artist, Venue, Event)
  if bipartite:
    node_colors = bipartite_node_coloring
  else:
    node_types, node_colors = np.unique(node_types, return_inverse=True)

  node_trace = go.Scatter(
      x=node_x, y=node_y, text=node_text,
      mode='markers',
      hoverinfo='text',
      marker=dict(
          showscale=False,
          colorscale='YlGnBu',
          reversescale=True,
          color=node_colors,
          size=10
          ),
          line_width=2)

  fig = go.Figure(data=[edge_trace, node_trace],
             layout=go.Layout(
                title=plot_title,
                titlefont_size=16,
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20,l=5,r=5,t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                )
  return fig