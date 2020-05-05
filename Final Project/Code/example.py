import musicbrainzngs
import general_methods as gen
import networkx as nx
from dateutil.relativedelta import relativedelta
import argparse
import pandas as pd
import configparser
import json

START_DATE = datetime.date(2015, 1, 1)
END_DATE = datetime.date.today()

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
  venue_mapper = gen.VenueMapper()
  venue_mapper.load_json('venue_mapping.json')

  valid_events, message = gen.get_mb_and_sl_events(test_mbid, mb_event_puller, sl_event_puller, venue_mapper,\
   START_DATE, END_DATE)

  print(message)

  venue_event_dict = {}
  all_events = []
  for event in valid_events:
    venue_id = gen.not_none(event.venue.id['mbid'], event.venue.id['slid'])
    if venue_mapper.has_id(venue_id):
      event.set_venue(venue_mapper.get_venue(venue_id))
    
    venue_mbid = event.venue.id['mbid']
    venue_slid = event.venue.id['slid']

    new_events = []
    new_key = (venue_mbid, venue_slid)
    if new_key not in venue_event_dict:
      new_events, message = gen.get_mb_and_sl_events(venue_mbid, mb_event_puller, sl_event_puller, venue_mapper, \
          START_DATE, END_DATE, seed_type="venue", slid=venue_slid, sl_page_limit=1)
      venue_event_dict[new_key] = new_events
      flattened_events = [x.flatten() for x in new_events]
      all_events += flattened_events

  venue_mapper.dump_json('venue_mapping_mod.json')
  all_events = [y for x in all_events for y in x]

  events_df = pd.DataFrame(all_events)
  print(gen.get_basic_artist_rec_from_df(events_df, test_mbid, with_geo=False))

if __name__ == "__main__":
  main()