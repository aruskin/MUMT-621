import musicbrainzngs
import requests
import fuzzywuzzy
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import math

import configparser # Only needed for stuff in main()
import argparse # Only needed for stuff in main()

#from https://gist.github.com/rochacbruno/2883505
def distance(origin, destination):
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371 # km

    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) \
        * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = radius * c

    return d

def match_venue_by_coordinates(venue_mbid, setlist_api_key, distance_threshold=25, match_threshold=80):
    mb_venue = musicbrainzngs.get_place_by_id(venue_mbid)
    mb_venue = mb_venue['place']

    matched_venue_dict = dict(mbid=mb_venue['id'], mb_name=mb_venue['name'], \
        venue_lat=None, venue_long=None, \
        slid=None, sl_name=None, \
        city_lat=None, city_long=None, city_name=None)

    if 'coordinates' in mb_venue:
        venue_lat = float(mb_venue['coordinates']['latitude'])
        venue_long = float(mb_venue['coordinates']['longitude'])
        matched_venue_dict['venue_lat'] = venue_lat
        matched_venue_dict['venue_long'] = venue_long

        # Search Setlist.fm venues by the name of the MB venue
        request = 'https://api.setlist.fm/rest/1.0/search/venues?name={}'.format(mb_venue['name'])
        headers = {'Accept': 'application/json', 'x-api-key': setlist_api_key}
        results = requests.get(request, headers=headers)
        json_results = results.json()

        if 'code' in json_results.keys():
            if json_results['code'] == 404:
                print('No match found in Setlist for venue {}'.format(mb_venue['name']))
        else:
            sleep_time = 1
            while 'venue' not in json_results.keys():
                time.sleep(sleep_time)
                print("Trying again...")
                results = requests.get(request, headers=headers)
                json_results = results.json() 
                sleep_time = sleep_time*1.5
            potential_matches = json_results['venue']

            # Calculate distance between query venue coords and city coords for each SL venue
            # Filter out SL venues with distance above threshold
            filter_matches = []
            for venue in potential_matches:
              if 'lat' in venue['city']['coords'].keys():
                city_lat = venue['city']['coords']['lat']
                city_long = venue['city']['coords']['long']
                if distance((venue_lat, venue_long), (city_lat, city_long)) < distance_threshold:
                   filter_matches.append(venue)
            potential_matches = filter_matches

            # Calculate match between venue names based on edit distance            
            best_match = match_threshold
            best_venue = {}
            for venue in potential_matches:
                fuzzy_match = fuzz.ratio(mb_venue['name'], venue['name'])
                if fuzzy_match > best_match:
                  best_venue = venue
            if bool(best_venue):
                matched_venue_dict['slid'] = best_venue['id']
                matched_venue_dict['sl_name'] = best_venue['name']
                matched_venue_dict['city_lat'] = best_venue['city']['coords']['lat']
                matched_venue_dict['city_long'] = best_venue['city']['coords']['long']
                matched_venue_dict['city_name'] = best_venue['city']['name']
    return matched_venue_dict

def add_to_venue_map(venue, venue_map):
    venue_entry = {}
    venue_entry['id'] = {'mbid': venue['mbid'], 'slid': venue['slid']}
    venue_entry['name'] = {'mbname': venue['mb_name'], 'slname': venue['sl_name']}
    venue_entry['city'] = {'name': venue['city_name'], 'coords': (venue['city_lat'], venue['city_long'])}
    venue_entry['coords'] = (venue['venue_lat'], venue['venue_long'])
    venue_map[venue['mbid']] = venue_entry
    venue_map[venue['slid']] = venue_entry

def main():
    musicbrainzngs.set_useragent(app="MusicBrainz to Setlist venue mapping", version="0")

    config = configparser.ConfigParser()
    config.read('.config')
    SETLIST_API_KEY = config['API Keys']['SETLIST_API_KEY']

    parser = argparse.ArgumentParser(description='MusicBrainz to Setlist venue mapping')
    parser.add_argument('mbid')
    args = parser.parse_args()
    venue_mbid = args.mbid # La Sala Rossa: 1808696e-b997-4b3c-91e7-37f09022ebe0

    print('Testing venue matching function...')
    matched_venue = match_venue_by_coordinates(venue_mbid, SETLIST_API_KEY)
    print(matched_venue)

    print('Testing venue map reformatting function...')
    venue_mapping_out = dict()
    add_to_venue_map(matched_venue, venue_mapping_out)
    print(venue_mapping_out)


if __name__ == "__main__":
  main()
