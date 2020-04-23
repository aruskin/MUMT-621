import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import pandas as pd
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

import musicbrainzngs
import musicbrainz_methods as mb
import general_methods as gen
import networkx as nx
import datetime
from dateutil.relativedelta import relativedelta

musicbrainzngs.set_useragent(app="testing MusicBrainz API", version="0")

# Copied from Dash tutorial - convert pandas dataframe to HTML table
def generate_table(dataframe, max_rows=10):
    return html.Table([
        html.Thead(
            html.Tr([html.Th(col) for col in dataframe.columns])
        ),
        html.Tbody([
            html.Tr([
                html.Td(dataframe.iloc[i][col]) for col in dataframe.columns
            ]) for i in range(min(len(dataframe), max_rows))
        ])
    ])

def get_artist_recs(test_mbid):
    test_mb_events = mb.get_musicbrainz_artist_events(test_mbid, verbose=False)

    events_to_use = []

    for event in test_mb_events:
        event_date = mb.try_parsing_mb_date(event['life-span']['begin'])
        if (event_date >= mb.START_DATE) & (event_date <= mb.END_DATE):
            events_to_use += [event]

    if len(events_to_use) > 0:
        G = nx.Graph()   #initialize graph
        mb.add_mb_events_to_bipartite_graph(events_to_use, G)

        # pull all other events held at same venue +/- two years of seed artist's event
        # add events, artists to graph
        venue_event_dict = dict()
        for event in events_to_use:
            if 'place-relation-list' in event.keys():
                for place_rel in event['place-relation-list']:
                    if place_rel['type'] == 'held at':
                        place_info = place_rel['place']
                        # don't try to repull all events if have multiple events at venue
                        if place_info['id'] not in venue_event_dict.keys():
                            new_events = mb.get_musicbrainz_venue_events(place_info['id'], verbose=False)
                            venue_event_dict[place_info['id']] = new_events
                            mb.add_mb_events_to_bipartite_graph(new_events, G)
        recs = gen.get_basic_artist_rec_from_bigraph(G, test_mbid)
    else: #No events found for artist
        recs = None
    return recs

# Copied this from Dash tutorial--will have to check if there's a more
# aesthetically pleasing stylesheet to use for this app
external_stylesheets = [dbc.themes.SKETCHY]

#########

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

server = app.server

app.layout = dbc.Container([
    html.H1(
        children='Get Artist Recommendations by Tour History',
        style={
            'textAlign': 'center'
        }
    ),
    html.Hr(),
    html.Label("Enter artist name:"),
    dcc.Input(id='artist-input', type='text', placeholder='e.g., Korpiklaani', value=""),
    html.Button(id='mbid-submit-button', children='Submit'),
    # intialize artist dropdown as hidden display
    html.Div(id='artist-dropdown-container',
        children=[dcc.Dropdown(id='artist-dropdown', placeholder='Select artist')], 
        style={'display': 'none'}),
     # Hidden divs inside the app that store intermediate values
    html.Div(id='mbid-entry-store', style={'display': 'none'}), 
    html.Div(id='mbid-valid-store', style={'display': 'none'}),
    html.Div(id='mbid-message'),
    html.Br(),
    html.Div(id='get-recs-container',
        children=[dbc.Button(id='get-recs-button', children='Find Related Artists'),
        dbc.Spinner(html.Div(id='get-recs-spinner'))],
        style={'display': 'none'}),
    #html.Div(id='get-recs-output'),
    html.Table(id='recs-table')
])

# When user enters artist name and hits submit button, we query MusicBrainz
# and populate dropdown list with the results 
# Display artist name and disambiguation (when available), and store associated
# MBID as value for dropdown options
@app.callback(
    [Output('mbid-message', 'children'), Output('artist-dropdown', 'options')],
    [Input('mbid-submit-button', 'n_clicks')],
    [State('artist-input', 'value')])
def update_artist_dropdown(n_clicks, artist_input_value):
    if n_clicks is None:
        raise PreventUpdate
    else:
        # This will still result in an error when empty input submitted
        # Need to figure out way around that
        if artist_input_value == "":
            message = "Please enter an artist name"
            return message, None
        else:
            try:
                result = musicbrainzngs.search_artists(artist=artist_input_value)
            except musicbrainzngs.WebServiceError as exc:
                message = "Something went wrong with the request: %s" % exc
                return message, None
            else:
                options = []
                num_artists = result['artist-count']
                for artist in result['artist-list']:
                    if 'disambiguation' in artist.keys():
                        artist_name = "{0} ({1})".format(artist['name'], artist['disambiguation'])
                    else:
                        artist_name = artist['name']
                    options += [{'label': artist_name, 'value': artist['id']}]
                message = "Found {} artists".format(num_artists)
                return message, options

# Only show artist dropdown list if/when candidate arists found
@app.callback(Output('artist-dropdown-container', 'style'),
    [Input('artist-dropdown', 'options')])
def toggle_artist_dropdown(artist_options):
    if artist_options is None:
        raise PreventUpdate
    else:
        if len(artist_options) == 0:
            return {'display': 'none'}
        else:
            return {'display': 'block'}

# When user selects option from dropdown list, update hidden elements for storing
# query MBID and whether it's valid (the validity thing may no longer be necessary...)
@app.callback(
    [Output('mbid-entry-store', 'children'), Output('mbid-valid-store', 'children'),
    Output('get-recs-container', 'style')],
    [Input('artist-dropdown', 'value')])
def update_mbid_outputs(artist_dropdown_selection):
    if artist_dropdown_selection is None:
        raise PreventUpdate
    else:
        return artist_dropdown_selection, True, {'display': 'block'}

# When user hits "Find Related Artists", generate list of recommendations based on
# query artist (need to have a valid MBID stored) and display in table
@app.callback(
    [Output('get-recs-spinner', 'children'), #Output('get-recs-output', 'children'), 
    Output('recs-table', 'children')],
    [Input('mbid-submit-button', 'n_clicks'), Input('get-recs-button', 'n_clicks')],
    [State('mbid-valid-store', 'children'), State('mbid-entry-store', 'children')]
    )
def update_recs_output(mbid_submit, recs_submit, mbid_valid, mbid_entry):
    if (mbid_submit is None) or (recs_submit is None):
        raise PreventUpdate
    else:
        if mbid_valid:
            recs = get_artist_recs(mbid_entry)
            if recs is None:
                return "No events found for {} between {} and {}".format(mbid_entry, mb.START_DATE, mb.END_DATE), None
            else:
                recs_table = generate_table(recs, len(recs))
                return "Getting recs for {}".format(mbid_entry), recs_table
        else:
            return "Need to enter valid MBID", None

if __name__ == '__main__':
    app.run_server(debug=True)