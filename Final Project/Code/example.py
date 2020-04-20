import musicbrainzngs
import musicbrainz_methods as mb
import general_methods as gen
import networkx as nx
from dateutil.relativedelta import relativedelta
import argparse

def main():
  musicbrainzngs.set_useragent(app="testing MusicBrainz API", version="0")
  parser = argparse.ArgumentParser(description='Get artist recommendations')
  parser.add_argument('mbid')
  args = parser.parse_args()
  test_mbid = args.mbid
  #test_mbid = "50eec634-7c42-41ee-9b1f-b41d9ca28b26" #Korpiklaani
  test_mb_events = mb.get_musicbrainz_artist_events(test_mbid, verbose=True)

  G = nx.Graph()   #initialize graph
  #mb.add_mb_events_to_graph(test_mb_events, G) #add all events for seed artist
  mb.add_mb_events_to_bipartite_graph(test_mb_events, G)

  # pull all other events held at same venue between start and end date
  # add events, artists to graph
  venue_event_dict = {}
  for event in test_mb_events:
    event_date = mb.try_parsing_mb_date(event['life-span']['begin'])
    if (event_date >= mb.START_DATE) & (event_date <= mb.END_DATE):
      if 'place-relation-list' in event.keys():
        for place_rel in event['place-relation-list']:
          if place_rel['type'] == 'held at':
            place_info = place_rel['place']
            # don't try to repull all events if have multiple events at venue
            if place_info['id'] not in venue_event_dict.keys():
              new_events = mb.get_musicbrainz_venue_events(place_info['id'], verbose=True)
              venue_event_dict[place_info['id']] = new_events
              mb.add_mb_events_to_bipartite_graph(new_events, G)

  # display graph!
  fig = gen.plot_network(G, test_mbid, bipartite=True)
  fig.show()

  print(gen.get_basic_artist_rec_from_bigraph(G, test_mbid))

if __name__ == "__main__":
  main()