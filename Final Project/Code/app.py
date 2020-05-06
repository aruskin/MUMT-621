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

SL_ARTIST_PAGE_LIMIT = 1
SL_VENUE_PAGE_LIMIT = 1

REC_COLUMNS = ["Artist", "Shared Venues"]

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
        ]

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
        dcc.Store(id='query-venues-store'),
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
    dbc.Button(id='get-recs-button', children='Find Related Artists', style={'display':'none'})
]

recs_output = html.Div(id='get-recs-container',
    children=[
        dbc.Row(dbc.Spinner(html.Div(id='get-recs-spinner1'), color="primary")),
        dbc.Row(dbc.Spinner(html.Div(id='get-recs-spinner2'), color="secondary")),
        dbc.Row(dbc.Col(dash_table.DataTable(id='recs-table', columns=[{"name": i, "id": i} for i in REC_COLUMNS]), 
            align='center'))
    ],
    style={'display': 'none'})

summary_cards = dbc.Row(
    [
        dbc.Col(dbc.Card([dbc.CardHeader("Summary"), dbc.CardBody(id='query-events-text')])),
        dbc.Col(dbc.Card([dbc.CardHeader("Mappability"), dbc.CardBody(id='query-map-text')])),
        dbc.Col(dbc.Card([dbc.CardHeader("More info about recommendations"), 
                dbc.CardBody(id='rec-select-text'), 
                dbc.CardLink(id='rec-select-mb-link')]))
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
            dbc.Row(dbc.Col(recs_output))
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
    Output('get-recs-button', 'style')],
    [Input('mbid-submit-button', 'n_clicks'), Input('artist-dropdown', 'value')])
def update_mbid_outputs(mbid_submit, artist_dropdown_selection):
    ctx = dash.callback_context
    if ctx.triggered:
        if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks":
            return None, False, {'display': 'none'}
        else:
            return artist_dropdown_selection, True, {'display': 'block'}
    else:
        raise PreventUpdate

@app.callback(
    Output('get-recs-container', 'style'),
    [Input('mbid-submit-button', 'n_clicks'), Input('get-recs-button', 'n_clicks')]
    )
def toggle_rec_area_visibility(mbid_submit, recs_submit):
    ctx = dash.callback_context
    if ctx.triggered:
        if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks":
            return {'display': 'none'}
        else:
            return {'display': 'block'}
    else:
        raise PreventUpdate


# Do first part of event pull - get events for query artist, update cards with summaries
@app.callback(
    [Output('get-recs-spinner1', 'children'), 
    Output('query-venues-store', 'data'), Output('query-events-text', 'children'), 
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
            events, message = gen.get_mb_and_sl_events(mbid_entry, \
                MB_EVENT_PULLER, SL_EVENT_PULLER, VENUE_MAPPER,\
                START_DATE, END_DATE, sl_page_limit=SL_ARTIST_PAGE_LIMIT)
            event_count = len(events)
            venue_list = []
            venue_count = 0

            for event in events:
                if event.venue not in venue_list:
                    venue_list.append(event.venue)
                    venue_count += 1
            summary_text = message + " {} events were found at {} unique venues.".format(event_count, venue_count)
            serializable_events = [event.to_dict() for event in events]
            events_json = json.dumps(serializable_events, default=str)
            map_plot, mappable_events, mappability_text = gen.generate_artist_events_map(events, mbid_entry)
            mappability_message = "{} events mapped.".format(mappable_events)
            if mappable_events < event_count:
                mappability_message = mappability_message +" No coordinates found for {}.".format(mappability_text)
            return "Pulled events for {}".format(mbid_entry), events_json, summary_text, mappability_message, map_plot
    else:
        raise PreventUpdate 

# When user hits "Find Related Artists", generate list of recommendations based on
# query artist (need to have a valid MBID stored) and display in table
@app.callback(
    [Output('get-recs-spinner2', 'children'), #Output('recs-table', 'children'), 
    Output('recs-table', 'data'), Output('recs-table', 'active_cell'), #Output('recs-table', 'columns'),
    Output('recs-state-store', 'children'), Output('venue-event-storage', 'data')],
    [Input('query-venues-store', 'data'), Input('mbid-entry-store', 'children'), Input('mbid-submit-button', 'n_clicks')],
    [State('recs-state-store', 'children')]
    )
def update_recs_output(events_json, mbid_entry, submit_clicks, recs_state_store):
    if (events_json is None) or (submit_clicks is None):
        raise PreventUpdate
    else: 
        ctx = dash.callback_context
        if ctx.triggered:
            if (ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks") or \
                ((ctx.triggered[0]['prop_id'] == "mbid-entry-store.children") and \
                (mbid_entry != recs_state_store)):
                return "Clearing recs...", [{}], None, None, None
            elif (ctx.triggered[0]['prop_id'] == "query-venues-store.data"):
                query_events_list = json.loads(events_json)

                events_list = gen.get_events_list(\
                    query_events_list, MB_EVENT_PULLER, SL_EVENT_PULLER, VENUE_MAPPER, \
                    START_DATE, END_DATE, SL_VENUE_PAGE_LIMIT)
                if len(events_list) > 0:
                    events_df = pd.DataFrame(events_list)
                    recs = gen.get_basic_artist_rec_from_df(events_df, mbid_entry, with_geo=False)
                    recs_table = recs.to_dict('records')
                    return "Got recs for {}".format(mbid_entry), recs_table, None, mbid_entry, events_list
                else:
                    return "No events found for {} between {} and {}".format(mbid_entry, START_DATE, END_DATE), [{}], None, mbid_entry, events_list
            elif (ctx.triggered[0]['prop_id'] == "mbid-entry-store.children") and (mbid_entry == recs_state_store):
                raise PreventUpdate

@app.callback(
    [Output('venue-events-table', 'children'), Output('venue-events-heading', 'children')],
    [Input('mbid-submit-button', 'n_clicks'), Input('artist-venue-map', 'hoverData')],
    [State('venue-event-storage', 'data')])
def update_venue_events_on_hover(mbid_submit, hover_data, events_list):
    ctx = dash.callback_context
    if ctx.triggered:
        if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks":
            return None, None
        else:
            if events_list is None:
                raise PreventUpdate
            else:
                chosen = [point["customdata"] for point in hover_data["points"]]
                venue_name, venue_id = chosen[0]

                events_df = pd.DataFrame(events_list)
                events_df['venue_mbid'] = events_df['venue_mbid'].fillna('')
                events_df['venue_slid'] = events_df['venue_slid'].fillna('')
                events_df['venue_id'] = list(zip(events_df.venue_mbid, events_df.venue_slid))
                events_df['event_date'] = events_df['time'].apply(lambda x:str(x))
                selected = events_df[events_df['venue_id'] == tuple(venue_id)]
                events_table = generate_table(selected[['event_date', 'artist_name']], len(selected))
                heading_text = 'Who else played {venue} between {start_date} and {end_date}?'.format(\
                    venue=venue_name, start_date=START_DATE, end_date=END_DATE)
                return events_table, heading_text

@app.callback([Output('rec-select-text', 'children'), Output('rec-select-mb-link', 'children'), Output('rec-select-mb-link', 'href')],
    [Input('mbid-submit-button', 'n_clicks'), Input('recs-table', 'active_cell')],
    [State('venue-event-storage', 'data'), State('recs-table', 'data')])
def display_recommended_artist_info(mbid_submit, active_cell, events_list, recs_table_data):
    ctx = dash.callback_context
    if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks":
        return None, None, None
    else:
        if active_cell is None:
            raise PreventUpdate
        else:
            active_row_id = active_cell['row_id']
            active_col_id = active_cell['column_id']
            selected_record = [x for x in recs_table_data if x['id']==active_row_id][0]
            artist = selected_record['Artist']
            artist_mbid = selected_record['id']
            shared_venues = selected_record['Shared Venues']
            if active_col_id == 'Artist':
                message = 'Find out more about {} !'.format(artist)
                mb_link_text = 'MusicBrainz artist page'
                mb_artist_page = 'https://musicbrainz.org/artist/' + artist_mbid
                return message, mb_link_text, mb_artist_page
            elif active_col_id == 'Shared Venues':
                relevant_events = [event for event in events_list if event['artist_mbid']==artist_mbid]
                event_text = ["{venue} ({date})".format(date=str(x['time']), \
                    venue=gen.not_none(x['venue_mbname'], x['venue_slname'])) for x in relevant_events]
                message = '{} and the query artist have recently played at {} of the same venues.'.format(artist, shared_venues)
                message = message + " {}'s events: ".format(artist)
                message = message + "; ".join(event_text)
                
                return message, None, None


if __name__ == '__main__':
    app.run_server(debug=True)