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
import json
import plotly.graph_objects as go

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

def get_query_artist_events(query_mbid):
    query_mb_events = mb.get_musicbrainz_artist_events(query_mbid, verbose=False)

    events_to_use = []

    for event in query_mb_events:
        event_date = mb.try_parsing_mb_date(event['life-span']['begin'])
        # Only use events that fall within date range
        if (event_date >= mb.START_DATE) & (event_date <= mb.END_DATE):
            # Only use events that have associated venues
            if 'place-relation-list' in event.keys():
                events_to_use += [event]
    return events_to_use

def generate_artist_events_map(query_artist_events, query_mbid):
    std_mb_events = [mb.map_mb_event_to_standard(event) for event in query_artist_events]
    std_mb_events =  [y for x in std_mb_events for y in x if y['artist_mbid']==query_mbid]
    mappable_events = [event for event in std_mb_events if 'venue_latitude' in event.keys()]
    if len(mappable_events) > 0:
        df = pd.DataFrame(mappable_events)
        df['text'] = df['artist_name'] + ' @ ' + df['venue_mb_name'] + \
            ' (' + df['time'].apply(lambda x: str(x.date())) + ')'
        events_by_venue_text = df.groupby(['venue_latitude', 'venue_longitude'])['text'].apply('<br>'.join)
        events_by_venue = df.groupby(['venue_latitude', 'venue_longitude']).size().to_frame(name="num_events")
        events_by_venue = events_by_venue.join(events_by_venue_text).reset_index()

        #max_events = events_by_venue['num_events'].max()
        #min_events = events_by_venue['num_events'].min()

        #MAX_MARKER_SIZE = 25
        #MIN_MARKER_SIZE = 5

        fig = go.Figure(data=go.Scattergeo(
            lon = events_by_venue['venue_longitude'],
            lat = events_by_venue['venue_latitude'],
            text = events_by_venue['text'],
            mode = 'markers',
            #marker = dict(
            #              line=dict(width=1, color='DarkSlateGrey'),
            #              size= (events_by_venue['num_events'] - min_events) * (MAX_MARKER_SIZE - MIN_MARKER_SIZE)/(max_events - min_events) + MIN_MARKER_SIZE)
            ))
        fig.update_geos(showcountries=True)
        return fig, len(mappable_events)
    else:
        return default_map_figure, 0


def get_artist_recs(query_artist_events, query_mbid):
    if len(query_artist_events) > 0:
        G = nx.Graph()   #initialize graph
        mb.add_mb_events_to_bipartite_graph(query_artist_events, G)

        # pull all other events held at same venue +/- two years of seed artist's event
        # add events, artists to graph
        venue_event_dict = dict()
        for event in query_artist_events:
        #    if 'place-relation-list' in event.keys():
                for place_rel in event['place-relation-list']:
                    if place_rel['type'] == 'held at':
                        place_info = place_rel['place']
                        # don't try to repull all events if have multiple events at venue
                        if place_info['id'] not in venue_event_dict.keys():
                            new_events = mb.get_musicbrainz_venue_events(place_info['id'], verbose=False)
                            venue_event_dict[place_info['id']] = new_events
                            mb.add_mb_events_to_bipartite_graph(new_events, G)
        recs = gen.get_basic_artist_rec_from_bigraph(G, query_mbid)
    else: #No events found for artist
        recs = None
    return recs

external_stylesheets = [dbc.themes.SKETCHY]

default_map_figure = go.Figure(go.Scattergeo())

#########

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

server = app.server

# Secret divs for intermediate value storage
secret_divs = [
        html.Div(id='mbid-entry-store', style={'display': 'none'}), 
        html.Div(id='mbid-valid-store', style={'display': 'none'}),
        html.Div(id='query-venues-store', style={'display': 'none'}),
        html.Div(id='recs-state-store', style={'display': 'none'})
    ]

# User input stuff
user_inputs = [
    html.Label("Enter artist name:"),
    dcc.Input(id='artist-input', type='text', placeholder='e.g., Korpiklaani', value=""),
    dbc.Button(id='mbid-submit-button', children='Submit'),
    # intialize artist dropdown as hidden display
    html.Div(id='artist-dropdown-container',
            children=[dcc.Dropdown(id='artist-dropdown', placeholder='Select artist')], 
            style={'display': 'none'}),
    html.Div(id='mbid-message'),
    html.Br(),
    html.Div(id='get-recs-container',
            children=[dbc.Button(id='get-recs-button', children='Find Related Artists'),
                    dbc.Spinner(html.Div(id='get-recs-spinner1'), color="primary"),
                    dbc.Spinner(html.Div(id='get-recs-spinner2'), color="secondary")],
            style={'display': 'none'})
]

summary_cards = dbc.Row(
    [
        dbc.Col(dbc.Card([dbc.CardHeader("# Valid Events"), dbc.CardBody(id='query-events-text')])),
        dbc.Col(dbc.Card([dbc.CardHeader("# Different Venues"), dbc.CardBody(id='query-venues-text')])),
        dbc.Col(dbc.Card([dbc.CardHeader("# Mappable Events"), dbc.CardBody(id='query-map-text')]))
    ]
)

app.layout = dbc.Container([
    html.H1(
        children='Get Artist Recommendations by Tour History',
        style={
            'textAlign': 'center'
        }
    ),
    html.Hr(),
    html.Div(secret_divs),
    html.Div(
        [dbc.Row([
            # 1st column: User input stuff
            dbc.Col(user_inputs, width='auto'),
            # 2nd column: summary of info about query artist
            dbc.Col([
                    summary_cards,
                    dbc.Row([dcc.Graph(id='artist-venue-map', figure=default_map_figure)], id='map-container')
                ],
                width='auto')
        ]),
        dbc.Row([html.Table(id='recs-table')])
        ]
    )
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

# Do first part of event pull - get events for query artist, update cards with summaries
@app.callback(
    [Output('get-recs-spinner1', 'children'), 
    Output('query-venues-store', 'children'), Output('query-events-text', 'children'), 
    Output('query-venues-text', 'children'), Output('query-map-text', 'children'), Output('artist-venue-map', 'figure')],
    [Input('mbid-submit-button', 'n_clicks'), Input('get-recs-button', 'n_clicks')],
    [State('mbid-valid-store', 'children'), State('mbid-entry-store', 'children')]
)
def update_summary_text(mbid_submit, recs_submit, mbid_valid, mbid_entry):
    ctx = dash.callback_context
    if ctx.triggered:
        if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks":
            return None, None, None, None, None, default_map_figure
        else:
            mbid_events = get_query_artist_events(mbid_entry)
            event_count = len(mbid_events)
            venue_set = set()

            for event in mbid_events:
                if 'place-relation-list' in event.keys():
                    for place_rel in event['place-relation-list']:
                        if place_rel['type'] == 'held at':
                            place_info = place_rel['place']
                            venue_set.add(place_info['id'])
            venue_count = len(venue_set)
            mbid_events_json = json.dumps(mbid_events)
            map_plot, mappable_events = generate_artist_events_map(mbid_events, mbid_entry)
            return "Pulled events for {}".format(mbid_entry), mbid_events_json, event_count, venue_count, mappable_events, map_plot
    else:
        raise PreventUpdate 

# When user hits "Find Related Artists", generate list of recommendations based on
# query artist (need to have a valid MBID stored) and display in table
@app.callback(
    [Output('get-recs-spinner2', 'children'), Output('recs-table', 'children'), Output('recs-state-store', 'children')],
    [Input('query-venues-store', 'children'), Input('mbid-entry-store', 'children'), Input('mbid-submit-button', 'n_clicks')],
    [State('recs-state-store', 'children')]
    )
def update_recs_output(mbid_events_json, mbid_entry, submit_clicks, recs_state_store):
    if (mbid_events_json is None) or (submit_clicks is None):
        raise PreventUpdate
    else: 
        ctx = dash.callback_context
        if ctx.triggered:
            #print(ctx.triggered[0]['prop_id'])
            if (ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks") or ((ctx.triggered[0]['prop_id'] == "mbid-entry-store.children") and (mbid_entry != recs_state_store)):
                return "Clearing recs...", None, None
            elif (ctx.triggered[0]['prop_id'] == "query-venues-store.children"):
                mbid_events_list = json.loads(mbid_events_json)
                recs = get_artist_recs(mbid_events_list, mbid_entry)
                if recs is None:
                    return "No events found for {} between {} and {}".format(mbid_entry, mb.START_DATE, mb.END_DATE), None, mbid_entry
                else:
                    recs_table = generate_table(recs, len(recs))
                    return "Got recs for {}".format(mbid_entry), recs_table, mbid_entry
            elif (ctx.triggered[0]['prop_id'] == "mbid-entry-store.children") and (mbid_entry == recs_state_store):
                raise PreventUpdate


if __name__ == '__main__':
    app.run_server(debug=True)