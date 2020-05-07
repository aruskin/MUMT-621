# Issues, Challenges, Limitations

## Songkick API
- Mapping between Songkick Artist IDs and MusicBrainz Artist IDs not one-to-one. Songkick may associate multiple MBIDs with one artist; as per [their documentation](https://www.songkick.com/developer/response-objects#artist-object), "It is possible that an artist has mutliple MusicBrainz IDs if we are not sure which is correct."
	- Example: Songkick associates the Russian folk metal band Arkona (Songkick ID: 232814) with MBIDs [9be897fc-6267-45ef-a745-22414d2fad3b (Polish electronic)](https://musicbrainz.org/artist/9be897fc-6267-45ef-a745-22414d2fad3b), [d7a18d20-8591-43af-b8e7-362eacc979f8 (Polish black metal)](https://musicbrainz.org/artist/d7a18d20-8591-43af-b8e7-362eacc979f8), and [baad262d-55ef-427a-83c7-f7530964f212 (the correct Arkona)](https://musicbrainz.org/artist/baad262d-55ef-427a-83c7-f7530964f212)
- The Songkick API allows you to pull past events by artist or user, but seemingly not by venue ([docs](https://www.songkick.com/developer/past-events)). However, you can pull upcoming events by venue ([docs](https://www.songkick.com/developer/upcoming-events)).

## Setlist.fm API
- Strict limits on the number of requests per second and per day
- Each event object associated with one artist; concerts with shared bills or festival stages will have separate event objects per artist
-It would be unreasonable to pull all events for venues on Setlist.fm (esp. given query throttling), but seemingly no way to explicitly add minimum and maximum date for request. Assume that the pages are ordered by date and limit ourselves to the first *n*.

## Visualization
- Experimented with artist-venue graph, but not sure how to make it meaningful when there are many nodes. Worth looking more into large-scale network graphs visualization methods.
- How to deal with super close together coordinates for user to select via hovering on map?
	- Even more problematic: multiple venues with same coords (e.g., plotted with city coordinates from Setlist.fm)?

## Built-in search functions
- MusicBrainz venue names like "O₂ Shepherd’s Bush Empire" - Setlist search function doesn't find any matches (but would for "O2 Shepherd's Bush Empire")
- Similarly, searching artist names with MusicBrainz API - only does exact matching? No results for "korpikaani" or "korpiklani", only "korpiklaani"

## Data consistency and accuracy
- Setlist.fm has incorrect coordinates (latitude and longitude) for Worthy Farm (Glastonbury) - associates with Pilton, Barnstaple (Devon) rather than Pilton, Somerset
	- More like this: for example, Leeds in Northern England given coordinates of Leeds (village) in Kent 
- Apparently can't rely on Setlist.fm events to always have associated city and city coordinates, esp. with recent virtual concerts due to pandemic
	- e.g., [this Zucchero concert](https://www.setlist.fm/setlist/zucchero/2020/private-venue-unknown-city-italy-3b86c4f0.html)
- Some MBIDs associated with Setlist.fm artists no longer exist in MusicBrainz
	- e.g., Future Punx (MBID abf8a9f4-ef46-4ec5-85fa-653d848dd057 on [Setlist artist page](https://www.setlist.fm/setlists/future-punx-6bc49ebe.html)), Lou-Adriane Cassidy (MBID b0de7c76-323b-43d7-9a57-2b61d870fb6c on [Setlist artist page](https://www.setlist.fm/setlists/lou-adriane-cassidy-2bf6d41e.html))
-MusicBrainz events with no associated artists, venues, dates

## Mapping venues between sources
- Venues with multiple incarnations in same city
- Venue complexes
- Festival stages