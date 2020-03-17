import musicbrainzngs
import musicbrainz_methods as mb
import networkx as nx
from dateutil.relativedelta import relativedelta

def main():
  musicbrainzngs.set_useragent(app="testing MusicBrainz API", version="0")
  test_mbid = "50eec634-7c42-41ee-9b1f-b41d9ca28b26" #Korpiklaani
  test_mb_events = mb.get_musicbrainz_artist_events(test_mbid)

  G = nx.Graph()   #initialize graph
  mb.add_mb_events_to_graph(test_mb_events, G) #add all events for seed artist

  # pull all other events held at same venue +/- two years of seed artist's event
  # add events, artists to graph
  for event in test_mb_events:
    event_date = mb.try_parsing_mb_date(event['life-span']['begin'])
    beg_date = event_date - relativedelta(years=2)
    end_date = event_date + relativedelta(years=2)
    if 'place-relation-list' in event.keys():
      for place_rel in event['place-relation-list']:
        if place_rel['type'] == 'held at':
          place_info = place_rel['place']
          new_events = mb.get_musicbrainz_venue_events(place_info['id'])
          mb.add_mb_events_to_graph(new_events, G, beg_date, end_date)

  # display graph!
  fig = mb.plot_network(G, test_mbid)
  fig.show()

if __name__ == "__main__":
  main()