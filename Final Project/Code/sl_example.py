import musicbrainz_methods as mb
import setlist_methods as sl
import general_methods as gen
import networkx as nx
import argparse
import configparser
import datetime

def main():
  #musicbrainzngs.set_useragent(app="testing MusicBrainz API", version="0")
  parser = argparse.ArgumentParser(description='Get artist recommendations')
  parser.add_argument('mbid')
  args = parser.parse_args()
  test_mbid = args.mbid

  config = configparser.ConfigParser()
  config.read('.config')
  SETLIST_API_KEY = config['API Keys']['SETLIST_API_KEY']

  #test_mbid = "50eec634-7c42-41ee-9b1f-b41d9ca28b26" #Korpiklaani
  test_sl_events = sl.get_setlist_events(test_mbid, SETLIST_API_KEY)

  G = nx.Graph()   #initialize graph
  sl.add_sl_events_to_bipartite_graph(test_sl_events, G)

  venue_event_dict = {}
  for event in test_sl_events:
    event_date = datetime.datetime.strptime(event['eventDate'], '%d-%m-%Y')
    if (event_date >= mb.START_DATE) & (event_date <= mb.END_DATE):
      place_info = event['venue']
      print(place_info['name'])
      if place_info['id'] not in venue_event_dict.keys():
        new_events = sl.get_setlist_events(place_info['id'], SETLIST_API_KEY, 'venue', limit=50)
        venue_event_dict[place_info['id']] = new_events
        sl.add_sl_events_to_bipartite_graph(new_events, G)
      

  # display graph!
  fig = gen.plot_network(G, test_mbid, bipartite=True)
  fig.show()

  print(gen.get_basic_artist_rec_from_bigraph(G, test_mbid))

if __name__ == "__main__":
  main()