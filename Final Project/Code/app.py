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

def generate_events_list(mbid_entry, artist_name):
    #event_pull_data = json.dumps([])
    query_events_list = []
    return_messages = dict(card_summary = "", progress_text = "")
    events, message = gen.get_mb_and_sl_events(mbid_entry, \
                MB_EVENT_PULLER, SL_EVENT_PULLER, VENUE_MAPPER,\
                START_DATE, END_DATE, sl_page_limit=SL_ARTIST_PAGE_LIMIT)
    #print(message)
    event_count = len(events)
    venue_count = 0

    if event_count > 0:
        # 1st part of pull - query artist events
        venue_list = []
        for event in events:
            if event.venue not in venue_list:
                venue_list.append(event.venue)
                venue_count += 1
        query_events_list = [event.to_dict() for event in events]
        #event_pull_data  = json.dumps(serializable_events, default=str)
        map_plot_out, mappable_events, mappability_text = gen.generate_artist_events_map(events, mbid_entry, default_map_figure)

        summary_text = message + " {} events were found at {} unique venues.".format(\
                            event_count, venue_count)
        mappability_message = "{} events mapped.".format(mappable_events)
        if mappable_events < event_count:
            mappability_message = mappability_message +" No coordinates found for {}.".format(mappability_text)
        card_text_out = html.P([summary_text, html.Hr(), mappability_message])
        return_messages['card_summary'] = card_text_out

        # 2nd part of pull - venue events
        events_list_out = gen.get_events_list(\
                query_events_list, MB_EVENT_PULLER, SL_EVENT_PULLER, VENUE_MAPPER, \
                START_DATE, END_DATE, SL_VENUE_PAGE_LIMIT)
        if len(events_list_out) > 0:
            events_df = pd.DataFrame(events_list_out)
            recs = gen.get_basic_artist_rec_from_df(events_df, mbid_entry)
            recs_table = recs.to_dict('records')
            return_messages['progress_text'] = "Got recommendations for {}".format(artist_name)
            #tooltip_toggle = TOGGLE_ON
    else: #no events found
        return_messages['progress_text'] = "No events found for {} between {} and {}, so no recommendations.".format(\
                    artist_name, START_DATE, END_DATE)
    #event_pull_entry = json.dumps(dict(mbid=mbid_entry, name=artist_name))
    return map_plot_out, recs_table, return_messages
#########

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

server = app.server

# Secret divs for intermediate value storage
secret_divs = [
    dcc.Store(id='mbid-entry-store'),
    dcc.Store(id='mbid-submission-store'),
    dcc.Store(id='init-event-pull-store'),
    dcc.Store(id='query-venues-store')
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

recs_output = html.Div(id='recs-out-container',
    children=[
        dbc.Row(dbc.Spinner(html.Div(id='get-recs-spinner1'), color="primary")),
        #dbc.Row(dbc.Spinner(html.Div(id='get-recs-spinner2'), color="secondary")),
        html.Div(id='recs-table-container', 
            children=[
                dbc.Row(html.H3("Top 10 Artists by Number of Shared Venues")),
                dbc.Row(dbc.Col(dash_table.DataTable(id='recs-table', 
                    columns=[{"name": i, "id": i} for i in REC_COLUMNS]),
                align='center'))
            ], style=TOGGLE_OFF),
        dbc.Tooltip("Click on a cell for more information!",
            target='recs-table-container')
    ],
    style=TOGGLE_OFF)

map_component = [
    dbc.Col([dcc.Graph(id='artist-venue-map', figure=default_map_figure, 
        config={'scrollZoom':True, 'showTips':True})], 
        id='map-container'),
    dbc.Tooltip("Click on a venue to see who else has played there!",
        target='map-container', hide_arrow=True, style=TOGGLE_OFF, id='map-tooltip')
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
            dbc.Row(dbc.Col(user_inputs)),
            dbc.Row(dbc.Col(recs_output))
        ], width=4),
        dbc.Col(dbc.Row(map_component))
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
    print('update_mbid_entry_store: MBID entry store: {}'.format(mbid_store_data))
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

# Called if Get Recs button clicked or selected artist changes
# Should help determine when to clear out various areas
@app.callback(
    [Output('mbid-submission-store', 'data'), Output('artist-venue-map', 'clickData')],
    [Input('get-recs-button', 'n_clicks'), Input('mbid-entry-store', 'data')])
def update_mbid_submit_store(submit_clicks, stored_entry):
    """
    Updates submitted artist store with value in selected artist store when Get Recs button clicked
    and clears out value when selected artist changes
    """
    ctx = dash.callback_context
    click_data_out = {'points':[], 'customdata':[]}

    if ctx.triggered[0]['prop_id'] == "get-recs-button.n_clicks":
        mbid_submit_data = stored_entry
    else:
        mbid_submit_data = json.dumps(dict(mbid=None, name=None))
    print('update_mbid_submit_store: MBID submit store: {}'.format(mbid_submit_data))
    return mbid_submit_data, click_data_out

# Toggling visibility of section with spinners and recommendation table - hide when Submit button 
# clicked, show when Find Related Artists button clicked
@app.callback(
    Output('recs-out-container', 'style'),
    [Input('mbid-submission-store', 'data')])

def toggle_rec_area_visibility(stored_mbid_entry):
    if (stored_mbid_entry is None):
        raise PreventUpdate
    else:
        toggle = TOGGLE_OFF
        mbid_entry_dict = json.loads(stored_mbid_entry)
        mbid_entry = mbid_entry_dict['mbid']

        if mbid_entry:
            toggle = TOGGLE_ON
        return toggle


@app.callback(
    [Output('init-event-pull-store', 'data'), 
    Output('get-recs-spinner1', 'children'), Output('artist-venue-map', 'figure'),
    Output('recs-table', 'data')],
    [Input('recs-out-container', 'style')],
    [State('mbid-submission-store', 'data'), State('init-event-pull-store', 'data'), 
    State('query-venues-store', 'data'), State('artist-venue-map', 'figure'),
    State('recs-table', 'data')]
    )
def update_recs_and_map(toggle, stored_mbid_entry, event_pull_entry, event_pull_data, current_map, current_recs_table):
    if (toggle == TOGGLE_OFF):
        raise PreventUpdate
    else:
        spinner_out = ""
        map_plot_out = default_map_figure
        recs_table = [{}]

        mbid_entry_dict = json.loads(stored_mbid_entry)
        mbid_entry = mbid_entry_dict['mbid']
        artist_name = mbid_entry_dict['name']
        print("update_recs_and_map: MBID entry: {}".format(mbid_entry))
        print("update_recs_and_map: init event pull store: {}".format(event_pull_entry))
        if event_pull_entry is None:
            event_entry = None
        else:
            event_entry_dict = json.loads(event_pull_entry)
            event_entry = event_entry_dict['mbid']

        if mbid_entry:
            if (event_entry is None) or (event_entry != mbid_entry):
                map_plot_out, recs_table, return_messages = generate_events_list(mbid_entry, artist_name)

                print(return_messages['card_summary'])

                spinner_out = return_messages['progress_text']
                event_pull_entry = json.dumps(dict(mbid=mbid_entry, name=artist_name))
            else:
                print("already pulled events for {}".format(artist_name))
                map_plot_out = current_map
                recs_table = current_recs_table
            #spinner_out = "Pulled events for {}".format(artist_name)
            #print(event_pull_data)
        return event_pull_entry, spinner_out, map_plot_out, recs_table

@app.callback(
    Output('recs-table-container', 'style'),
    [Input('mbid-submission-store', 'data'), Input('init-event-pull-store', 'data')]
    )
def toggle_recs_table(stored_mbid_entry, event_pull_entry):
    if (stored_mbid_entry is None):
        raise PreventUpdate
    else:
        toggle = TOGGLE_OFF
        mbid_entry_dict = json.loads(stored_mbid_entry)
        mbid_entry = mbid_entry_dict['mbid']

        print("toggle_recs_table: MBID submit store: {}".format(mbid_entry))
        if mbid_entry:
            if event_pull_entry is None:
                event_entry = None
            else:
                event_entry_dict = json.loads(event_pull_entry)
                event_entry = event_entry_dict['mbid']
            print("toggle_recs_table: event pull store: {}".format(event_entry))

            if mbid_entry == event_entry:
                print("here!")
                toggle = TOGGLE_ON
        return toggle


if __name__ == '__main__':
    app.run_server(debug=True)