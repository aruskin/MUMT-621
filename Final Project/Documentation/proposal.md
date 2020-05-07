
# Final Project Proposal

## Goal
To create a prototype of an artist recommendation system based on event and venue data

## Motivation
Music festivals and concerts with shared bills can provide attendees with the opportunity to discover new artists that they might not have found through existing recommendation systems. For example, Le Guess Who? is a Dutch music festival featuring international artists performing in different genres, and the festival’s website has a page for each artist with suggestions of other artists in the line-up that “You might also like”. The artist page for Shortparis (Russia) suggests that fans of the band may also want to see Los Pirañas (Colombia), Lalalar (Turkey), Italia 90 (UK) at the 2020 edition of the festival.[<sup>1</sup>](#1) In contrast, Spotify's "Related artists" for each of those bands all appear to be groups that perform in the same language (e.g., Russian for Shortparis[<sup>2</sup>](#2), Spanish for Los Pirañas[<sup>3</sup>](#3)). Spotify’s artist recommendations are “based on analysis of the Spotify community’s listening history.”[<sup>4</sup>](#4) It’s unclear how Le Guess Who? came up with their recommendations, but the results suggest that festival line-ups could be used to generate more geographically and linguistically diverse sets of recommendations. Venues and their past events could be seen as loose proxies for groups of users and their listening history, particularly for venues or festivals that tend to draw a certain type of act (e.g., metal bars, EDM festivals). The existence of crowdsourced databases of event data, such as Musicbrainz, Songkick, and Setlist.fm, with different scopes and levels of coverage should make it possible to aggregate festival line-ups and shared bills involving an artist of interest and automate the process of discovering new artists or local scenes from live events. 

<a class="anchor" id="1"><sup>1</sup></a> https://www.leguesswho.nl/lineup/shortparis

<a class="anchor" id="2"><sup>2</sup></a>: https://open.spotify.com/artist/61j4FFbKlzdYihMtpM1hZD/related

<a class="anchor" id="3"><sup>3</sup></a>: https://open.spotify.com/artist/1TWdamQsAiOgB0szQsMSeq/related

<a class="anchor" id="4"><sup>4</sup></a>: https://developer.spotify.com/documentation/web-api/reference/artists/get-related-artists/


## Related Work
Music recommendation systems are a major topic in the music information retrieval literature. Celma (2010) provides an overview of the music recommendation task and common approaches, including methods for collaborative filtering (based on user listening habits or ratings), context-based filtering (based on cultural information, such as tags), content-based filtering (based on analyses of the audio content), and hybrid methods. The recommendation system proposed in this project can be seen as a context-based recommendation system, since it does not rely on user data or audio features. We can also envision this as one component of a hybrid approach in future work—e.g., using event and venue data to identify a set of artists that can then be used for content-based playlist generation. Schedl et al. (2018) provide a more recent review of the remaining challenges in music recommendation. In particular, they discuss the cold start problem, in which systems have difficulty generating recommendations for new users with no listening history and recommending new items with no ratings. Our proposed approach would be one way of avoiding the first part of the cold start problem, since it does not rely on user listening behavior or ratings, but it does require artists to have some history of touring in order to be recommended.

Some recent papers have used musical event data to address various research questions. Krasanakis et al. (2018) used event data from Facebook and artist information from Spotify to explore the relationship between artist and venue popularity. Arakelyan et al. (2018) used Songkick event data for three different tasks: forecasting artist success, predicting the venues at which an artist will perform, and joint discovery of influential artists and venues. Both projects model the artist and venue network as a graph and make use of bipartite graph algorithms, which we also intend to do for this project. Akimchuk et al. (2019) explored the possibility of using event data from Ticketfly and Facebook to build a local music recommendation system. They discuss popularity bias in recommender systems and how that prevents more obscure artists from being recommended in collaborative-filtering systems, which relates to the motivation for this project. Finally, Allik et al. (2018) present MusicLynx, a graph-based system for artist discovery. In MusicLynx, artists are linked  by different types of relationships mined from sources like MusicBrainz, DBpedia, AcousticBrainz, Last.fm, and Wikidata, and presented as a color-coded graph for the user to explore. For this project, we’re only interested in the relationships between artists and events or venues (e.g., linking artists that have played together, artists that have played at the same venue within a certain timeframe), but may take inspiration from the MusicLynx user interface and visualization methods.


## Proposed deliverables (from highest to lowest priority)
1. Interface that allows user to enter artist query and get back list of related artists
2. Interactive visualizations of artist/event/venue information
3. Analysis of different sources of event data 


## Partial Bibliography

Akimchuk, Daniel, Timothy Clerico, and Douglas Turnbull. 2019. “Evaluating Recommender System Algorithms for Generating Local Music Playlists.” https://arxiv.org/abs/1907.08687

Allik, Alo, Florian Thalmann, and Mark Sandler. 2018. “MusicLynx: Exploring Music Through Artist Similarity Graphs.” In *Companion Proceedings of the The Web Conference 2018 (WWW ’18)*, 167–170. https://doi.org/10.1145/3184558.3186970

Arakelyan, Shushan,  Fred Morstatter, Margaret Martin, Emilio Ferrara, and Aram Galstyan. 2018. “Mining and Forecasting Career Trajectories of Music Artists.” In *HT ’18: 29th ACM Conference on Hypertext and Social Media*. https://doi.org/10.1145/3209542.3209554

Celma, Òscar. 2010. “Music Recommendation.” In *Music Recommendation and Discovery: The Long Tail, Long Fail, and Long Play in the Digital Music Space*, 43–85. Springer, Berlin, Heidelberg. https://doi.org/10.1007/978-3-642-13287-2_3

Krasanakis, Emmanouil, Emmanouil Schinas, Symeon Papadopoulos, Yiannis Kompatsiaris, and Pericles Mitkas. 2018. “VenueRank: Identifying Venues that Contribute to Artist Popularity.” In *Proceedings of the 19th International Society for Music Information Retrieval Conference (ISMIR 2018)*, 702–708. https://doi.org/10.5281/zenodo.1492513

Schedl, Markus, Hamed Zamani, Ching-Wei Chen, Yashar Deldjoo, and Mehdi Elahi. 2018. “Current Challenges and Visions in Music Recommender Systems Research.” *International Journal of Multimedia Information Retrieval* 7 (2): 95–116.

