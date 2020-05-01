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

START_DATE = mb.START_DATE
END_DATE = mb.END_DATE

# Copied from Dash tutorial - convert pandas dataframe to HTML table
def generate_table(dataframe, max_rows=10):
    return \
        [
                        html.Thead(
                            html.Tr([html.Th(col) for col in dataframe.columns])
                        ),
                        html.Tbody([
                            html.Tr([html.Td(dataframe.iloc[i][col]) for col in dataframe.columns]) \
                            for i in range(min(len(dataframe), max_rows))
                        ])
        ]#)

# Only keep events that fall within date range, have venues and artists associated w/them
def filter_mb_events(mb_events, start_date=START_DATE, end_date=END_DATE):
    valid_events = []
    for event in mb_events:
        event_date = mb.try_parsing_mb_date(event['life-span']['begin'])
        if (event_date >= start_date) & (event_date <= end_date):
            if ('place-relation-list' in event.keys()) and ('artist-relation-list' in event.keys()):
                valid_events += [event]
    return valid_events

# Pull MusicBrainz events for the query artist and filter to valid events
def get_query_artist_events(query_mbid):
    query_mb_events = mb.get_musicbrainz_artist_events(query_mbid, verbose=False)
    valid_events = filter_mb_events(query_mb_events)
    return valid_events

# Create geographical plot of query artist events with lat/long
# Returns plot object, number of events plotted, text summarizing events not plotted
def generate_artist_events_map(query_artist_events, query_mbid):
    std_mb_events = [mb.map_mb_event_to_standard(event) for event in query_artist_events]
    std_mb_events =  [y for x in std_mb_events for y in x if y['artist_mbid']==query_mbid]
    mappable_events = [event for event in std_mb_events if 'venue_latitude' in event.keys()]
    non_mappable_events = [event for event in std_mb_events if event not in mappable_events]
    non_mappable_text = ["{artist} @ {venue} ({date})".format(date=str(x['time'].date()), \
        artist=x['artist_name'], venue=x['venue_mb_name']) for x in non_mappable_events]
    non_mappable_text = "; ".join(non_mappable_text)
    if len(mappable_events) > 0:
        df = pd.DataFrame(mappable_events)
        df['text'] = df['artist_name'] + ' @ ' + df['venue_mb_name'] + \
            ' (' + df['time'].apply(lambda x: str(x.date())) + ')'
        events_by_venue_text = df.groupby(['venue_latitude', 'venue_longitude'])['text'].apply('<br>'.join)
        events_by_venue = df.groupby(['venue_mb_id', 'venue_mb_name', 'venue_latitude', 'venue_longitude']).size().to_frame(name="num_events")
        events_by_venue = events_by_venue.join(events_by_venue_text).reset_index()

        #max_events = events_by_venue['num_events'].max()
        #min_events = events_by_venue['num_events'].min()

        #MAX_MARKER_SIZE = 25
        #MIN_MARKER_SIZE = 5

        fig = go.Figure(data=go.Scattergeo(
            lon = events_by_venue['venue_longitude'],
            lat = events_by_venue['venue_latitude'],
            text = events_by_venue['text'],
            customdata = events_by_venue[['venue_mb_name', 'venue_mb_id']].apply(tuple, axis=1),
            mode = 'markers',
            marker = dict(line=dict(width=1, color='DarkSlateGrey'))
            #              ,size= (events_by_venue['num_events'] - min_events) * (MAX_MARKER_SIZE - MIN_MARKER_SIZE)/(max_events - min_events) + MIN_MARKER_SIZE)
            ))
        fig.update_geos(showcountries=True)
        return fig, len(mappable_events), non_mappable_text
    else:
        return default_map_figure, 0, non_mappable_text

def get_venue_event_dict(query_artist_events):
    venue_event_dict = dict()
    for event in query_artist_events:
        for place_rel in event['place-relation-list']:
            if place_rel['type'] == 'held at':
                place_info = place_rel['place']
                if place_info['id'] not in venue_event_dict.keys():
                    new_events = mb.get_musicbrainz_venue_events(place_info['id'], verbose=False)
                    valid_new_events = filter_mb_events(new_events)
                    venue_event_dict[place_info['id']] = valid_new_events
    return venue_event_dict


def get_artist_recs(venue_event_dict, query_mbid):
    if venue_event_dict: # False if dict is empty
        G = nx.Graph()
        for venue_id, events_list in venue_event_dict.items():
            mb.add_mb_events_to_bipartite_graph(events_list, G)
        recs = gen.get_basic_artist_rec_from_bigraph(G, query_mbid)
    else: #No events found for artist
        recs = None
    return recs

external_stylesheets = [dbc.themes.SKETCHY]

# Empty map figure (note: no country borders)
default_map_figure = go.Figure(go.Scattergeo())

#########

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

server = app.server

# Secret divs for intermediate value storage
secret_divs = [
        html.Div(id='mbid-entry-store', style={'display': 'none'}), 
        html.Div(id='mbid-valid-store', style={'display': 'none'}),
        html.Div(id='query-venues-store', style={'display': 'none'}),
        html.Div(id='recs-state-store', style={'display': 'none'}),
        dcc.Store(id='venue-event-storage')
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
        dbc.Col(dbc.Card([dbc.CardHeader("Summary"), dbc.CardBody(id='query-events-text')])),
        #dbc.Col(dbc.Card([dbc.CardHeader("# Different Venues"), dbc.CardBody(id='query-venues-text')])),
        dbc.Col(dbc.Card([dbc.CardHeader("Mappability"), dbc.CardBody(id='query-map-text')]))
    ]
)

header = [
    html.H1('Get Artist Recommendations by Tour History',
        style={'textAlign': 'center'})
    ]

app.layout = dbc.Container([
    dbc.Row([dbc.Col(header)]),
    html.Div(secret_divs),
    dbc.Row([
        # 1st column: User input stuff & recs output table
        dbc.Col([
            dbc.Row(dbc.Col(user_inputs)),
            dbc.Row([dbc.Table(id='recs-table', hover=True)])
        ], width=4),
        # 2nd column: summary of info about query artist & map
        dbc.Col([
            summary_cards,
            dbc.Row([
                dbc.Col([dcc.Graph(id='artist-venue-map', figure=default_map_figure)], id='map-container', width='auto')
            ]),
            dbc.Row([html.H3(id='venue-events-heading')]),
            dbc.Row([dbc.Table(id='venue-events-table')])
            ], width=8)
        ])
    ], fluid=True)

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
    Output('query-map-text', 'children'), Output('artist-venue-map', 'figure')],
    [Input('mbid-submit-button', 'n_clicks'), Input('get-recs-button', 'n_clicks')],
    [State('mbid-valid-store', 'children'), State('mbid-entry-store', 'children')]
)
def update_summary_text(mbid_submit, recs_submit, mbid_valid, mbid_entry):
    ctx = dash.callback_context
    if ctx.triggered:
        if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks":
            return None, None, None, None, default_map_figure
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
            summary_text = "On MusicBrainz: {events} events found at {venues} \
                unique venues between {beg_date} and {end_date}".format(\
                    events=event_count, venues=venue_count, \
                    beg_date=START_DATE.date(), end_date=END_DATE.date())
            mbid_events_json = json.dumps(mbid_events)
            map_plot, mappable_events, mappability_text = generate_artist_events_map(mbid_events, mbid_entry)
            mappability_message = "{} events mapped.".format(mappable_events)
            if mappable_events < event_count:
                mappability_message = mappability_message +" No coordinates found for {}.".format(mappability_text)
            return "Pulled events for {}".format(mbid_entry), mbid_events_json, summary_text, mappability_message, map_plot
    else:
        raise PreventUpdate 

# When user hits "Find Related Artists", generate list of recommendations based on
# query artist (need to have a valid MBID stored) and display in table
@app.callback(
    [Output('get-recs-spinner2', 'children'), Output('recs-table', 'children'), 
    Output('recs-state-store', 'children'), Output('venue-event-storage', 'data')],
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
                return "Clearing recs...", None, None, None
            elif (ctx.triggered[0]['prop_id'] == "query-venues-store.children"):
                mbid_events_list = json.loads(mbid_events_json)
                venue_event_dict = get_venue_event_dict(mbid_events_list)
                recs = get_artist_recs(venue_event_dict, mbid_entry)
                if recs is None:
                    return "No events found for {} between {} and {}".format(mbid_entry, START_DATE, END_DATE), None, mbid_entry, venue_event_dict
                else:
                    recs_table = generate_table(recs, len(recs))
                    return "Got recs for {}".format(mbid_entry), recs_table, mbid_entry, venue_event_dict
            elif (ctx.triggered[0]['prop_id'] == "mbid-entry-store.children") and (mbid_entry == recs_state_store):
                raise PreventUpdate

@app.callback(
    [Output('venue-events-table', 'children'), Output('venue-events-heading', 'children')],
    [Input('mbid-submit-button', 'n_clicks'), Input('artist-venue-map', 'hoverData')],
    [State('venue-event-storage', 'data')])
def update_venue_events_on_hover(mbid_submit, hover_data, venue_event_dict):
    ctx = dash.callback_context
    if ctx.triggered:
        if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks":
            return None, None
        else:
            if venue_event_dict is None:
                raise PreventUpdate
            else:
                chosen = [point["customdata"] for point in hover_data["points"]]
                venue_name, venue_mbid = chosen[0]

                events = venue_event_dict[venue_mbid]

                std_events = [mb.map_mb_event_to_standard(event) for event in events]
                std_events =  [y for x in std_events for y in x]
                events_df = pd.DataFrame(std_events)
                events_df['date'] = events_df['time'].apply(lambda x: str(x.date()))
                events_table = generate_table(events_df[['date', 'artist_name']], len(events_df))
                heading_text = 'Who else played {venue} between {start_date} and {end_date}?'.format(\
                    venue=venue_name, start_date=START_DATE.date(), end_date=END_DATE.date())
                return events_table, heading_text

if __name__ == '__main__':
    app.run_server(debug=True)