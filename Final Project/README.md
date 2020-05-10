# Artist Recommendations Based on Event Data

## Getting Started

### Using the demo

Try out the Heroku deployment of the app [here](https://mumt-app.herokuapp.com/)

### Running the app locally

Set up a folder and a [Python virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/) within that folder

Set up a [Setlist.fm](https://www.setlist.fm/) account and apply for an API key

Download `app.py`, `general_methods.py`, `requirements.txt`, and `venue_mapping.json` from `Code` to the folder

Create a file called `.config` in the folder with the following contents (replacing "whatever" with your Setlist.fm API key):

```
[API Keys]
SETLIST_API_KEY=whatever
```

With the virtual environment activated, install the requirements with `pip install -r requirements.txt` 

Run the app (from the activated virtual environment) with `python app.py`

### How to use the app

1. Type the name of the artist you want to get recommendations for in the text box
2. Hit the "Submit" button. If one or more matching artists have been found in the MusicBrainz database, a dropdown list of artist names will appear--select your intended artist from here. Note that the search function is fairly sensitive to spacing (e.g., [Shortparis](https://musicbrainz.org/artist/e1f95266-0e43-4e25-9415-0596cb711d7b) won't show up in the [search results for "short paris"](https://musicbrainz.org/search?query=short+paris&type=artist)) and spelling (e.g., [Korpiklaani](https://musicbrainz.org/artist/50eec634-7c42-41ee-9b1f-b41d9ca28b26) won't show up in the [search results for "korpiklani"](https://musicbrainz.org/search?query=korpiklani&type=artist)), but not capitalization.
3. Once you've selected an artist from the dropdown list, the "Find Related Artists" button will appear. Hit this button to start generating a list of recommendations, or go back to steps 1 or 2 to change your artist selection.
4. If the selected artist has recent events in MusicBrainz and/or Setlist.fm, the text in the "Summary" and "Mappability" cards with more information about those, and the mappable venues will appear on the map plot. While the recommendations are being generated, you can hover over the venues on the map to see their names and the dates the artist played there.
5. Once the recommendations have been generated, a table with the top 10 artists by number of shared venues with the selected artist will appear. You can click on the cells of the table in the "Artist" column to find out more about the recommended artist and in the "Shared Venues" column to see a list of the venues the recommended artist also played at. If you click on venues on the map, a table of the recent events at that venue will appear under the map figure.


## What Else is in Here?

### Code

- [venue-mapping](Code/venue-mapping/): Utilities for generating mapping between venues from MusicBrainz and Setlist.fm
- [example.py](Code/example.py): Do one-off runs of recommendation system from the CLI

### Documentation

- Formal write-ups and slide presentation for class
	- [Initial project proposal](Documentation/proposal.md)
	- [Presentation slides](Documentation/Project presentation.pdf)
	- [Abstract and bibliography](Documentation/project_abstract_and_full_bibliography.md)
	- [Final software project description](Documentation/software_project_description.md)
- [Lots of issues and next steps!](Documentation/issues.md) 

