import musicbrainzngs
import datetime
import networkx as nx
from dateutil.relativedelta import relativedelta
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
def get_musicbrainz_artist_events(mbid, verbose=True, limit=100, offset=0):
    events = []
    page = 1
    if verbose:
      print("fetching page number %d.." % page)
    # Get all events linked to an area, an artist or a place.
    result = musicbrainzngs.browse_events(artist=mbid, includes=["event-rels", "place-rels", "artist-rels"], limit=limit, offset=offset)
    events_list = result['event-list']
    events += events_list
    if "event_count" in result:
      count = result['event-count']
      if verbose:
        print("")
    while len(events_list) >= limit:
      #do something
      offset += limit
      page += 1 
      if verbose:
        print("fetching page number %d.." % page)
      result = musicbrainzngs.browse_events(artist=mbid, includes=["event-rels", "place-rels", "artist-rels"], limit=limit, offset=offset)
      events_list = result['event-list']
      events += events_list
    if verbose:
      print("")
      print("\n%d events on  %d pages" % (len(events), page))
    return events

# Get all of the MusicBrainz events associated with a particular venue
# Returns list of dictionaries
def get_musicbrainz_venue_events(mbid, verbose=True, limit=100, offset=0):
    events = []
    page = 1
    if verbose:
      print("fetching page number %d.." % page)
    # Get all events linked to an area, an artist or a place.
    result = musicbrainzngs.browse_events(place=mbid, includes=["event-rels", "place-rels", "artist-rels"], limit=limit, offset=offset)
    events_list = result['event-list']
    events += events_list
    if "event_count" in result:
      count = result['event-count']
      if verbose:
        print("")
    while len(events_list) >= limit:
      #do something
      offset += limit
      page += 1 
      if verbose:
        print("fetching page number %d.." % page)
      result = musicbrainzngs.browse_events(place=mbid, includes=["event-rels", "place-rels", "artist-rels"], limit=limit, offset=offset)
      events_list = result['event-list']
      events += events_list
    if verbose:
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

def map_mb_event_to_standard(event):
  events = []
  for artist in event['artist-relation-list']:
    new_event = dict()
    artist_info = artist['artist']
    new_event['artist_name'] = artist_info['name']
    new_event['artist_mbid'] = artist_info['id']
    if 'type' in artist.keys():
      new_event['artist_event_relationship'] = artist['type']
    new_event['time'] = try_parsing_mb_date(event['life-span']['begin'])
    if 'place-relation-list' in event.keys():
        for place_rel in event['place-relation-list']:
          if place_rel['type'] == 'held at':
            place_info = place_rel['place']
            new_event['venue_mb_id'] = place_info['id']
            new_event['venue_mb_name'] = place_info['name']
            if 'coordinates' in place_info.keys():
              new_event['venue_latitude'] = place_info['coordinates']['latitude']
              new_event['venue_longitude'] = place_info['coordinates']['longitude']
    new_event['event_type'] = event['type']
    new_event['event_mb_name'] = event['name']
    new_event['event_mb_id'] = event['id']
    events.append(new_event)
  return events