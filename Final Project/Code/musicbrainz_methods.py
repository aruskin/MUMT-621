import musicbrainzngs
import datetime
import networkx as nx
from dateutil.relativedelta import relativedelta
import plotly.graph_objects as go
import numpy as np

START_DATE = datetime.datetime.strptime('2015-01-01', '%Y-%m-%d')
END_DATE = datetime.datetime.today()

def try_parsing_mb_date(text):
    for fmt in ('%Y-%m-%d', '%Y-%m', '%Y'):
        try:
            return datetime.datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError('no valid date format found')

# Get all of the MusicBrainz events associated with a particular artist
# Returns list of dictionaries
def get_musicbrainz_artist_events(mbid, limit=100, offset=0):
    events = []
    page = 1
    print("fetching page number %d.." % page)
    # Get all events linked to an area, an artist or a place.
    result = musicbrainzngs.browse_events(artist=mbid, includes=["event-rels", "place-rels", "artist-rels"], limit=limit, offset=offset)
    events_list = result['event-list']
    events += events_list
    if "event_count" in result:
      count = result['event-count']
      print("")
    while len(events_list) >= limit:
      #do something
      offset += limit
      page += 1 
      print("fetching page number %d.." % page)
      result = musicbrainzngs.browse_events(artist=mbid, includes=["event-rels", "place-rels", "artist-rels"], limit=limit, offset=offset)
      events_list = result['event-list']
      events += events_list
    print("")
    print("\n%d events on  %d pages" % (len(events), page))
    return events

# Get all of the MusicBrainz events associated with a particular venue
# Returns list of dictionaries
def get_musicbrainz_venue_events(mbid, limit=100, offset=0):
    events = []
    page = 1
    print("fetching page number %d.." % page)
    # Get all events linked to an area, an artist or a place.
    result = musicbrainzngs.browse_events(place=mbid, includes=["event-rels", "place-rels", "artist-rels"], limit=limit, offset=offset)
    events_list = result['event-list']
    events += events_list
    if "event_count" in result:
      count = result['event-count']
      print("")
    while len(events_list) >= limit:
      #do something
      offset += limit
      page += 1 
      print("fetching page number %d.." % page)
      result = musicbrainzngs.browse_events(place=mbid, includes=["event-rels", "place-rels", "artist-rels"], limit=limit, offset=offset)
      events_list = result['event-list']
      events += events_list
    print("")
    print("\n%d events on  %d pages" % (len(events), page))
    return events

def add_mb_events_to_graph(mb_events, G, start_date=START_DATE, end_date=END_DATE):
  for event in mb_events:
    event_date = try_parsing_mb_date(event['life-span']['begin'])
    if (event_date >= start_date) & (event_date <= end_date):
      G.add_node(event['id'], name=event['name'], node_type="Event", date=event_date)
      if 'type' in event.keys():
        if event['type'] == 'Concert':
          edge_weight = 2
        else:
          edge_weight = 1
      if 'artist-relation-list' in event.keys():
        for artist in event['artist-relation-list']:
          artist_info = artist['artist']
          if 'type' in artist_info.keys():
            if artist_info['type'] == 'main performer':
              edge_weight += 0.5
          G.add_node(artist_info['id'], name=artist_info['name'], node_type="Artist", bipartite=0)
          G.add_edge(artist_info['id'], event['id'], weight=edge_weight)
          #ignore relationship to event (e.g., main act vs support) for now
      if 'place-relation-list' in event.keys():
        for place_rel in event['place-relation-list']:
          if place_rel['type'] == 'held at':
            place_info = place_rel['place']
            G.add_node(place_info['id'], name=place_info['name'], node_type="Venue", bipartite=1)
            G.add_edge(event['id'], place_info['id'])

def add_mb_events_to_bipartite_graph(mb_events, G, start_date=START_DATE, end_date=END_DATE):
  for event in mb_events:
    event_date = try_parsing_mb_date(event['life-span']['begin'])
    if (event_date >= start_date) & (event_date <= end_date):
      if 'place-relation-list' in event.keys():
        for place_rel in event['place-relation-list']:
          if place_rel['type'] == 'held at':
            place_info = place_rel['place']
            G.add_node(place_info['id'], name=place_info['name'], node_type="Venue")
      if 'artist-relation-list' in event.keys():
        for artist in event['artist-relation-list']:
          artist_info = artist['artist']
          G.add_node(artist_info['id'], name=artist_info['name'], node_type="Artist")
          G.add_edge(artist_info['id'], place_info['id'])

def plot_network(G, mbid, bipartite=False):
  if bipartite:
    artist_nodes = {n for n, d in G.nodes(data=True) if d['node_type']=='Artist'}
    pos = nx.layout.bipartite_layout(G, artist_nodes)
  else:
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
  for node in G.nodes():
      x, y = G.nodes[node]['pos']
      node_x.append(x)
      node_y.append(y)
      # Every node should have a human readable name associated with it
      text = G.nodes[node]['name'] + "<br>Type: {}".format(G.nodes[node]['node_type'])
      if 'date' in G.nodes[node].keys():
          text = text + "<br>Date: {}".format(G.nodes[node]['date'])
      node_text.append(text)
      if node == mbid:
        node_types.append('Seed')
        seed_artist = G.nodes[node]['name']
      else:
        node_types.append(G.nodes[node]['node_type'])
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
                title='<br>Network graph for {}'.format(seed_artist),
                titlefont_size=16,
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20,l=5,r=5,t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                )
  return fig

# Return list of artists with the most overlapping venues as query artist
# (Doesn't take into account how often they've played at these venues,
# whether they've shared bill with query artist, etc.)
# Assume bipartite graph of artist-venue data
def get_basic_artist_rec(bi_G, query_id, n_recs=10):
  venues, artists = nx.bipartite.sets(bi_G)
  venue_degrees, artist_degrees = nx.bipartite.degrees(bi_G, artists)
  artists_ranked = [(k, v) for k, v in sorted(artist_degrees, key=lambda item: item[1], reverse=True) \
                    if k != query_id]
  num_venues = len(venues)
  outlist = artists_ranked[:n_recs]
  outlist = [(bi_G.nodes[x]['name'], y/num_venues) for x, y in outlist]
  return outlist