# Issues, Challenges, Limitations

## Heroku deployment
- Different handling of resources than when running locally in Dash development environment--need to look into this more to handle issues dealing with multiple processes in a reasonable way.

## Dealing with APIs

### Retrieving events by date range
- Neither the MusicBrainz nor the Setlist.fm API allow users to directly filter the date range of events pulled. The page number of the events pulled (by artist or venue) can be specified, and in Setlist.fm, events seem to be ordered such that the most recent events will be in the first page of results. Due to the Setlist.fm API limitations on the rate and number of queries, we simply use the first 5 pages of results (up to 100 events) for the initial artist events and 2 pages of results (up to 40 events) for the events by venue; this method should give us the most recent Setlist.fm events for the query artist and their venues, but may not retrieve all of the events between the given start and end date. We retrieve all of the events for the query artist and venues queried with MusicBrainz and then filter by date range, since the volume of events in the MusicBrainz database is much lower and the MusicBrainz API does not have a strict limitation on queries.

### Songkick API
- Mapping between Songkick Artist IDs and MusicBrainz Artist IDs not one-to-one. Songkick may associate multiple MBIDs with one artist; as per [their documentation](https://www.songkick.com/developer/response-objects#artist-object), "It is possible that an artist has mutliple MusicBrainz IDs if we are not sure which is correct."
	- Example: Songkick associates the Russian folk metal band Arkona (Songkick ID: 232814) with MBIDs [9be897fc-6267-45ef-a745-22414d2fad3b (Polish electronic)](https://musicbrainz.org/artist/9be897fc-6267-45ef-a745-22414d2fad3b), [d7a18d20-8591-43af-b8e7-362eacc979f8 (Polish black metal)](https://musicbrainz.org/artist/d7a18d20-8591-43af-b8e7-362eacc979f8), and [baad262d-55ef-427a-83c7-f7530964f212 (the correct Arkona)](https://musicbrainz.org/artist/baad262d-55ef-427a-83c7-f7530964f212)
- The Songkick API allows you to pull past events by artist or user, but seemingly not by venue ([docs](https://www.songkick.com/developer/past-events)). However, you can pull upcoming events by venue ([docs](https://www.songkick.com/developer/upcoming-events)).

### Setlist.fm API
- Strict limits on the number of requests per second and per day
- Each event object associated with one artist; concerts with shared bills or festival stages will have separate event objects per artist
- Classical music events: who counts as the artist for symphonic concerts? One might be interested in getting recommendations based on conductor, ensemble, featured soloist...but how are the events stored?
	- [Zubin Mehta](https://www.setlist.fm/setlists/zubin-mehta-33d5d4cd.html), [Israel Philharmonic Orchestra, Zubin Mehta](https://www.setlist.fm/setlists/israel-philharmonic-orchestra-zubin-mehta-63dbe68f.html)
	- [Results of searching for Marin Alsop in Setlist.fm web interface](https://www.setlist.fm/search?query=marin+alsop): no artist events for conductor
	- Classical music events don't seem to be a priority for Setlist.fm contributors, though
- Built-in search function limited - Setlist search function doesn't find any matches for "O₂ Shepherd’s Bush Empire" (but would for "O2 Shepherd's Bush Empire")

### MusicBrainz API
- Built-in search function limited - searching artist names with MusicBrainz API only does exact matching? No results for "korpikaani" or "korpiklani", only "korpiklaani"


## Map visualization
### Data issues
- Many MusicBrainz venues lacking latitude and longitude information
- Setlist.fm venues have coordinates for the city the venue is in, but not the venue itself; as a result, different venues within the same city may be plotted in the exact same spot. 
- Inaccurate city coordinates in Setlist.fm (see "Data consistency and accuracy" section)

### Readability
- Future work may include using more sophisticated mapping methods to better display different venues located within the same city. 
	- Is Mapbox the answer? The way MusicBrainz shows Places by Area (e.g., [Montreal](https://musicbrainz.org/area/c3cc624e-b963-49cf-ad0b-e318cb341963/places)) seems like a good model

## Other visualizations
- Experimented with artist-venue graph, but not sure how to make it meaningful when there are many nodes. Worth looking more into large-scale network graphs visualization methods.

## Data consistency and accuracy
- Setlist.fm has incorrect coordinates (latitude and longitude) for Worthy Farm (Glastonbury) - associates with Pilton, Barnstaple (Devon) rather than Pilton, Somerset
	- More like this: for example, Leeds in Northern England given coordinates of Leeds (village) in Kent 
- Apparently can't rely on Setlist.fm events to always have associated city and city coordinates, esp. with recent virtual concerts due to pandemic
	- e.g., [this Zucchero concert](https://www.setlist.fm/setlist/zucchero/2020/private-venue-unknown-city-italy-3b86c4f0.html)
- Some MBIDs associated with Setlist.fm artists no longer exist in MusicBrainz
	- e.g., Future Punx (MBID abf8a9f4-ef46-4ec5-85fa-653d848dd057 on [Setlist artist page](https://www.setlist.fm/setlists/future-punx-6bc49ebe.html)), Lou-Adriane Cassidy (MBID b0de7c76-323b-43d7-9a57-2b61d870fb6c on [Setlist artist page](https://www.setlist.fm/setlists/lou-adriane-cassidy-2bf6d41e.html))
- MusicBrainz events with no associated artists, venues, dates
- MusicBrainz area relationships (for venue location, artist area of origin) at different levels of granularity

## Mapping venues between sources
- Multiple MusicBrainz venues could map to same Setlist.fm venue using the logic in `venue_mapping.py`. For example:
	- [Metropolitan Opera House (1883-1966)](https://musicbrainz.org/place/364049a0-810c-45e4-80ee-666e6da8f76f) and [Metropolitan Opera House (1966-)](https://musicbrainz.org/place/0d6d636e-2e13-4655-a9d9-6dd3765f841d) both map to [the old incarnation of the venue in Setlist.fm](https://www.setlist.fm/venue/metropolitan-opera-house-new-york-ny-usa-4bd6cb0a.html). Even though the venue's location changed, the name and city coordinates haven't; would need some additional logic to do mapping to Setlist.fm venues correctly for this case.
	- [Westfallenhalle 1 ](https://musicbrainz.org/place/bd6deeb3-b55f-400e-8569-c0847a40c1a4), [Westfallenhalle 2](https://musicbrainz.org/place/a3b38a39-b231-4d9b-b812-3cf939875956), [Westfallenhallen](https://musicbrainz.org/place/925286c2-18a6-419e-ac08-fd0c589ee70d) all map to [Westfallenhalle in Setlist.fm](https://www.setlist.fm/venue/westfalenhalle-dortmund-germany-73d61e71.html)
- Tricky venues
	- Venues with multiple incarnations in same city
	- Venue complexes 
	- Festival stages
- Since area associated with MusicBrainz venue isn't guaranteed to be a city, difficult to match by area name without further crawling of MB relationships
	- e.g. [La Sala Rossa](https://musicbrainz.org/place/1808696e-b997-4b3c-91e7-37f09022ebe0) in Le Plateau-Mont-Royal on MB, just Montreal in [Setlist.fm](https://www.setlist.fm/venue/la-sala-rossa-montreal-qc-canada-3d635d3.html)

## Usability
### User input of artist name
- The two-step process requiring a user to type in an artist’s name and then select the artist from a dropdown list can be tedious. It ensures that the system is using the MBID unambiguously tied to the user’s intended artist without requiring the user to find the artist’s MBID themselves. For example, when more than one artist shares the same name, the MusicBrainz artist entries will generally have disambiguating information (e.g., “Slaves (Punk duo from Kent, UK)” versus “Slaves (US post-hardcore band)”), so we allow the user to identify the artist rather than making any assumptions for them. But is it necessary when only 1 result is returned from MusicBrainz?
