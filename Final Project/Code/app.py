import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import dash_table
import pandas as pd
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

import musicbrainzngs
import general_methods as gen
import networkx as nx
import datetime
from dateutil.relativedelta import relativedelta
import json
import plotly.graph_objects as go
import configparser
import os

musicbrainzngs.set_useragent(app="testing MusicBrainz API", version="0")

# Global variables and objects
is_prod = os.environ.get('IS_HEROKU', None) # running production or development?

if is_prod: #use Heroku environment vars
    SETLIST_API_KEY = os.environ.get('SETLIST_API_KEY') 
else: #running locally, read in vars from config file
    config = configparser.ConfigParser()
    config.read('.config')
    SETLIST_API_KEY = config['API Keys']['SETLIST_API_KEY']

START_DATE = datetime.date(2015, 1, 1)
END_DATE = datetime.date.today()

MB_EVENT_PULLER = gen.MusicBrainzPuller(app="MUMT-621 Project testing", version="0")
SL_EVENT_PULLER = gen.SetlistPuller(api_key=SETLIST_API_KEY)
VENUE_MAPPER = gen.VenueMapper()
VENUE_MAPPER.load_json('venue_mapping.json')

SL_ARTIST_PAGE_LIMIT = 2
SL_VENUE_PAGE_LIMIT = 1

REC_COLUMNS = ["Artist", "Shared Venues"]

TOGGLE_ON = {'display': 'block'}
TOGGLE_OFF = {'display': 'none'}

external_stylesheets = [dbc.themes.SKETCHY]

# Empty map figure (note: no country borders)
default_map_figure = go.Figure(data=go.Scattergeo(),
    layout=go.Layout(autosize=True, margin=go.layout.Margin(l=0, r=0, t=0, b=0),
        showlegend=False))

# Copied from Dash tutorial - convert pandas dataframe to HTML table
def generate_table(dataframe, max_rows=10):
    return \
        [
                        html.Thead(
                            html.Tr([html.Th(col) for col in dataframe.columns])
                        ),
                        html.Tbody([
                            html.Tr([html.Td(dataframe.iloc[i][col]) for col in dataframe.columns])\
                            for i in range(min(len(dataframe), max_rows))
                        ])
        ]
#########

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

server = app.server

# Secret divs for intermediate value storage
secret_divs = [
        dcc.Store(id='mbid-entry-store')
    ]

# User input stuff - text box for artist name, submission button, dropdown for results
user_inputs = [
    html.Label("Enter artist name:"),
    dcc.Input(id='artist-input', type='text', placeholder='e.g., Korpiklaani', value=""),
    dbc.Button(id='mbid-submit-button', children='Submit'),
    # intialize artist dropdown as hidden display
    html.Div(id='artist-dropdown-container',
            children=[dcc.Dropdown(id='artist-dropdown', placeholder='Select artist')], 
            style=TOGGLE_OFF),
    html.Div(id='mbid-message'),
    html.Br(),
    dbc.Button(id='get-recs-button', children='Find Related Artists', style=TOGGLE_OFF)
]

header = [
    html.H1('Get Artist Recommendations by Tour History',
        style={'textAlign': 'center'})
    ]

app.layout = dbc.Container([
    dbc.Row([dbc.Col(header)]),
    html.Div(secret_divs),
    dbc.Row([
        # 1st column: user input options
        dbc.Col([
            dbc.Row(dbc.Col(user_inputs))
        ], width=4)
    ])
])

###############
# Callbacks!

# Called every time MBID submit button clicked
@app.callback(
    [Output('mbid-message', 'children'), Output('artist-dropdown', 'options'),
    Output('artist-dropdown', 'value')],
    [Input('mbid-submit-button', 'n_clicks')],
    [State('artist-input', 'value')])
def update_artist_dropdown_options(n_clicks, artist_input_value):
    """
    Each time user hits Submit button, use entry from text box to query MusicBrainz and populate 
    drodpdown list with results (matching artists). Display artist name and disambiguation (when 
    available) and store associated MBID as value for dropdown options.

    Keyword arguments:
    n_clicks -- number of times Submit button has been clicked, None if never clicked
    artist_input_value -- current value typed in "Enter artist name:" text box
    """
    if n_clicks is None:
        raise PreventUpdate
    else:
        mbid_message = ""
        artist_dropdown_options = []
        artist_dropdown_selection = None
        if artist_input_value == "":
            mbid_message = "Please enter an artist name"
        else:
            try:
                result = musicbrainzngs.search_artists(artist=artist_input_value)
            except musicbrainzngs.WebServiceError as exc:
                mbid_message = "Something went wrong with the request: %s" % exc
            else:
                num_artists = result['artist-count']
                for artist in result['artist-list']:
                    if 'disambiguation' in artist.keys():
                        artist_name = "{0} ({1})".format(artist['name'], artist['disambiguation'])
                    else:
                        artist_name = artist['name']
                    artist_dropdown_options += [{'label': artist_name, 'value': artist['id']}]
                mbid_message = "Found {} artists".format(num_artists)
        return html.P(mbid_message), artist_dropdown_options, artist_dropdown_selection

# Called whenever artist dropdown menu options change
@app.callback(Output('artist-dropdown-container', 'style'),
    [Input('artist-dropdown', 'options')])
def update_artist_dropdown_visibility(artist_dropdown_options):
    """
    Determine when to show the artist dropdown menu component--hide when no options to display.

    Keyword arguments:
    artist_dropdown_options -- list of options in artist dropdown menu
    """
    if artist_dropdown_options is None:
        raise PreventUpdate
    else:
        if len(artist_dropdown_options) == 0:
            return TOGGLE_OFF
        else:
            return TOGGLE_ON

# Called whenever selected value in artist dropdown changes
@app.callback(
    Output('mbid-entry-store', 'data'),
    [Input('artist-dropdown', 'value')],
    [State('artist-dropdown', 'options')])
def update_mbid_entry_store(artist_dropdown_selection, artist_dropdown_options):
    """
    Update MBID entry store with name and MBID of artist currently selected from dropdown.
    
    Keyword arguments:
    artist_dropdown_selection -- currently selected value from artist dropdown menu
    artist_dropdown_options -- all options in artist dropdown menu (labels and values)
    """
    mbid_store_dict = dict(mbid=None, name=None)
    if artist_dropdown_selection:
        selected = [x['label'] for x in artist_dropdown_options \
            if x['value'] == artist_dropdown_selection]
        mbid_store_dict['mbid'] = artist_dropdown_selection
        mbid_store_dict['name'] = selected[0]
    mbid_store_data = json.dumps(mbid_store_dict)
    print('MBID entry store: {}'.format(mbid_store_data))
    return mbid_store_data

# Called whenever MBID entry store value changes
@app.callback(
    Output('get-recs-button', 'style'),
    [Input('mbid-entry-store', 'data')])
def toggle_recs_button_visibility(stored_entry):
    """
    Determine when to show Get Recommendations button. Display when user has selected artist from
    dropdown, hide otherwise.

    Keyword arguments:
    stored_entry -- current data stored in MBID entry store
    """
    if (stored_entry is None):
        raise PreventUpdate
    else:
        toggle = TOGGLE_OFF
        mbid_entry_dict = json.loads(stored_entry)
        mbid_entry = mbid_entry_dict['mbid']
        if mbid_entry:
            toggle = TOGGLE_ON
        return toggle

if __name__ == '__main__':
    app.run_server(debug=True)