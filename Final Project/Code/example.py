import musicbrainzngs
import musicbrainz_methods as mb
import general_methods as gen
import networkx as nx
from dateutil.relativedelta import relativedelta
import argparse
import pandas as pd
import configparser

def main():
  config = configparser.ConfigParser()
  config.read('.config')
  SETLIST_API_KEY = config['API Keys']['SETLIST_API_KEY']
  parser = argparse.ArgumentParser(description='Get artist recommendations')
  parser.add_argument('mbid')
  args = parser.parse_args()
  test_mbid = args.mbid
  #test_mbid = "50eec634-7c42-41ee-9b1f-b41d9ca28b26" #Korpiklaani

  mb_event_puller = gen.MusicBrainzPuller(app="MUMT-621 Project testing", version="0")
  sl_event_puller = gen.SetlistPuller(api_key=SETLIST_API_KEY)

  valid_events, mapped_venues = gen.get_mb_and_sl_events(test_mbid, mb_event_puller, sl_event_puller,\
   mb.START_DATE, mb.END_DATE)

  print("{} valid events".format(len(valid_events)))

  venue_event_dict = {}
  venue_traversed = {}
  all_events = []
  for event in valid_events:
    venue_id = gen.not_none(event.venue.id['mbid'], event.venue.id['slid'])
    if venue_id in mapped_venues:
      event.set_venue(mapped_venues[venue_id])
    
    venue_mbid = event.venue.id['mbid']
    venue_slid = event.venue.id['slid']

    #pull_mbid = venue_mbid and (venue_mbid not in venue_traversed)
    #pull_slid = venue_slid and (venue_slid not in venue_traversed)

    new_events = []
    new_key = (venue_mbid, venue_slid)
    if new_key not in venue_event_dict:
    #if pull_mbid or pull_slid:
      #if pull_mbid and pull_slid:
      new_events, new_mapped_venues = gen.get_mb_and_sl_events(venue_mbid, mb_event_puller, sl_event_puller, \
          mb.START_DATE, mb.END_DATE, seed_type="venue", slid=venue_slid, sl_page_limit=2)
      #venue_event_dict[(venue_mbid, venue_slid)] = new_events
      #   venue_traversed[venue_mbid] = True
      #   venue_traversed[venue_slid] = True
      # elif pull_mbid and not pull_slid:
      #   new_events = gen.get_mb_and_sl_events(venue_mbid, mb_event_puller, sl_event_puller, \
      #       mb.START_DATE, mb.END_DATE, seed_type="venue")
      #   venue_traversed[venue_mbid] = True
      #   check_key = (None, venue_slid)
      #   if check_key in venue_event_dict:
      #     new_key = (venue_mbid, venue_slid)
      #     new_events = gen.merge_event_lists(new_events, venue_event_dict[check_key])
      #     del venue_event_dict[check_key]
      # elif pull_slid and not pull_mbid:
      #   new_events = gen.get_mb_and_sl_events(None, mb_event_puller, sl_event_puller, \
      #     mb.START_DATE, mb.END_DATE, seed_type="venue", slid=venue_slid, sl_page_limit=2)
      #   venue_traversed[venue_slid] = True
      #   check_key = (venue_mbid, None)
      #   if check_key in venue_event_dict:
      #     new_key = (venue_mbid, venue_slid)
      #     new_events = gen.merge_event_lists(new_events, venue_event_dict[check_key])
      #     del venue_event_dict[check_key]
      venue_event_dict[new_key] = new_events
      flattened_events = [x.flatten() for x in new_events]
      all_events += flattened_events
      #mapped_venues.update(new_mapped_venues)
      #for event in valid_new_events:
      #  event.add_to_bigraph(G)

  # display graph!
  #fig = gen.plot_network(G, test_mbid, bipartite=True)
  #fig.show()
  print(mapped_venues)
  #print(gen.get_basic_artist_rec_from_bigraph(G, test_mbid))
  all_events = [y for x in all_events for y in x]

  events_df = pd.DataFrame(all_events)
  print(gen.get_basic_artist_rec_from_df(events_df, test_mbid, with_geo=False))

if __name__ == "__main__":
  main()