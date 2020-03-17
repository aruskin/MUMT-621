
# Final Project Proposal

## Goal
To create a prototype of an artist recommendation system based on event and venue data

## Motivation
Music festivals and concerts with shared bills can provide attendees with the opportunity to discover new artists that they might not have found through existing recommendation systems. For example, Le Guess Who? is a Dutch music festival featuring international artists performing in different genres, and the festival’s website has a page for each artist with suggestions of other artists in the line-up that “You might also like”. The artist page for Shortparis (Russia) suggests that fans of the band may also want to see Los Pirañas (Colombia), Lalalar (Turkey), Italia 90 (UK) at the 2020 edition of the festival.[^1] In contrast, Spotify's "Related artists" for each of those bands all appear to be groups that perform in the same language (e.g., Russian for Shortparis,[^2] Spanish for Los Pirañas[^3]). Spotify’s artist recommendations are “based on analysis of the Spotify community’s listening history.”[^4] It’s unclear how Le Guess Who? came up with their recommendations, but the results suggest that festival line-ups could be used to generate more geographically and linguistically diverse sets of recommendations. The existence of crowdsourced databases of event data, such as Musicbrainz, Songkick, and Setlist.fm, with different scopes and levels of coverage should make it possible to aggregate festival line-ups and shared bills involving an artist of interest and automate the process of discovering new artists or local scenes from live events. 

## Related Work
Some recent papers have used musical event data to address various research questions. Krasanakis et al. (2018) used event data from Facebook and artist information from Spotify to explore the relationship between artist and venue popularity. Arakelyan et al. (2018) used Songkick event data for three different tasks: forecasting artist success, predicting the venues at which an artist will perform, and joint discovery of influential artists and venues. Both projects model the artist and venue network as a graph and make use of bipartite graph algorithms, which we also intend to do for this project. Akimchuk et al. (2019) explored the possibility of using event data from Ticketfly and Facebook to build a local music recommendation system. They discuss popularity bias in recommender systems and how that prevents more obscure artists from being recommended in collaborative-filtering systems, which relates to the motivation for this project. Finally, Allik et al. (2018) present MusicLynx, a graph-based system for artist discovery. In MusicLynx, artists are linked  by different types of relationships mined from sources like MusicBrainz, DBpedia, AcousticBrainz, Last.fm, and Wikidata, and presented as a color-coded graph for the user to explore. For this project, we’re only interested in the relationships between artists and events or venues (e.g., linking artists that have played together, artists that have played at the same venue within a certain timeframe), but may take inspiration from the MusicLynx user interface and visualization methods.

## Proposed deliverables (from highest to lowest priority)
1. Interface that allows user to enter artist query and get back list of related artists
	* Combine event data from APIs of multiple sources
	* Rank artists based on similarity of events/venues played
2. Interactive visualizations of artist/event/venue information
	* Network-based (allow user to explore clusters, identify “scenes”)
	* Map-based (show venues in geographical context)
3. Analysis of different sources of event data 
	* Compare metadata schemes
	* Compare scope and coverage (try to identify differences by geography, genre, etc.)


[^1]: https://www.leguesswho.nl/lineup/shortparis
[^2]: https://open.spotify.com/artist/61j4FFbKlzdYihMtpM1hZD/related
[^3]: https://open.spotify.com/artist/1TWdamQsAiOgB0szQsMSeq/related
[^4]: https://developer.spotify.com/documentation/web-api/reference/artists/get-related-artists/


## Partial Bibliography

Akimchuk, Daniel, Timothy Clerico, and Douglas Turnbull. 2019. “Evaluating Recommender System Algorithms for Generating Local Music Playlists.” https://arxiv.org/abs/1907.08687

Allik, Alo, Florian Thalmann, and Mark Sandler. 2018. “MusicLynx: Exploring Music Through Artist Similarity Graphs.” In *Companion Proceedings of the The Web Conference 2018 (WWW ’18)*, 167–170. https://doi.org/10.1145/3184558.3186970

Arakelyan, Shushan,  Fred Morstatter, Margaret Martin, Emilio Ferrara, and Aram Galstyan. 2018. “Mining and Forecasting Career Trajectories of Music Artists.” In *HT ’18: 29th ACM Conference on Hypertext and Social Media*. https://doi.org/10.1145/3209542.3209554

Krasanakis, Emmanouil, Emmanouil Schinas, Symeon Papadopoulos, Yiannis Kompatsiaris, and Pericles Mitkas. 2018. “VenueRank: Identifying Venues that Contribute to Artist Popularity.” In *Proceedings of the 19th International Society for Music Information Retrieval Conference (ISMIR 2018)*, 702–708. https://doi.org/10.5281/zenodo.1492513
