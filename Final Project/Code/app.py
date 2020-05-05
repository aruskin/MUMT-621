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
    SETLIST_API_KEY = os.environment.get('SETLIST_API_KEY') 
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

# Create geographical plot of query artist events with lat/long
# Returns plot object, number of events plotted, text summarizing events not plotted
def generate_artist_events_map(query_artist_events, query_mbid):
    std_events = [event.flatten() for event in query_artist_events]
    std_events =  [y for x in std_events for y in x if y['artist_mbid']==query_mbid]
    mappable_events = [event for event in std_events if ('venue_lat' in event) or ('city_lat' in event)]
    non_mappable_events = [event for event in std_events if event not in mappable_events]
    
    # All setlist venues should have city coordinates - only MB venues would be non-mappable
    non_mappable_text = ["{artist} @ {venue} ({date})".format(date=str(x['time']), \
        artist=x['artist_name'], venue=x['venue_mbname']) for x in non_mappable_events]
    non_mappable_text = "; ".join(non_mappable_text)

    for event in mappable_events:
        if event['venue_lat']: #not None
            event['venue_name'] = event['venue_mbname']
            event['coord_type'] = 'venue'
            event['lat'] = event['venue_lat']
            event['lon'] = event['venue_long']
        else:
            event['venue_name'] = event['venue_slname']
            event['coord_type'] = 'city'
            event['lat'] = event['city_lat']
            event['lon'] = event['city_long']

    if len(mappable_events) > 0:
        df = pd.DataFrame(mappable_events)
        df['text'] = df['artist_name'] + ' @ ' + df['venue_name'] + \
            ' (' + df['time'].apply(lambda x: str(x)) + ')' + '<br>Mapped using '+\
            df['coord_type'] + ' coordinates.'

        df['venue_mbid'] = df['venue_mbid'].fillna('')
        df['venue_slid'] = df['venue_slid'].fillna('')
        df['venue_id'] = list(zip(df.venue_mbid, df.venue_slid))
        df_grouped = df.groupby(['venue_name', 'venue_id', 'lat', 'lon'])
        events_by_venue_text = df_grouped['text'].agg(lambda x:'<br>'.join(x))
        events_by_venue = events_by_venue_text.reset_index()

        fig = go.Figure(data=go.Scattergeo(
            lon = events_by_venue['lon'],
            lat = events_by_venue['lat'],
            text = events_by_venue['text'],
            customdata = events_by_venue[['venue_name', 'venue_id']].apply(tuple, axis=1),
            mode = 'markers',
            marker = dict(line=dict(width=1, color='DarkSlateGrey'))
            ))
        fig.update_geos(showcountries=True)
        return fig, len(mappable_events), non_mappable_text
    else:
        return default_map_figure, 0, non_mappable_text

def get_events_list(query_artist_events):
    venue_event_dict = {}
    all_events = []
    for event_dict in query_artist_events:
        event = gen.Event()
        event.from_dict(event_dict)
        venue_id = gen.not_none(event.venue.id['mbid'], event.venue.id['slid'])
        if VENUE_MAPPER.has_id(venue_id):
          event.set_venue(VENUE_MAPPER.get_venue(venue_id))
        
        venue_mbid = event.venue.id['mbid']
        venue_slid = event.venue.id['slid']

        new_events = []
        new_key = (venue_mbid, venue_slid)
        if new_key not in venue_event_dict:
          new_events, message = gen.get_mb_and_sl_events(venue_mbid, \
            MB_EVENT_PULLER, SL_EVENT_PULLER, VENUE_MAPPER, \
            START_DATE, END_DATE, seed_type="venue", slid=venue_slid, \
            sl_page_limit=SL_VENUE_PAGE_LIMIT)
          venue_event_dict[new_key] = new_events
          flattened_events = [x.flatten() for x in new_events]
          all_events += flattened_events
    all_events = [y for x in all_events for y in x]
    return all_events

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
    html.Div(id='get-recs-container',
            children=[dbc.Button(id='get-recs-button', children='Find Related Artists'),
                    dbc.Spinner(html.Div(id='get-recs-spinner1'), color="primary"),
                    dbc.Spinner(html.Div(id='get-recs-spinner2'), color="secondary")],
            style={'display': 'none'})
]

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
            dbc.Row(
                #[dbc.Table(id='recs-table', hover=True)]
                [dbc.Col(dash_table.DataTable(id='recs-table'), # row_selectable='single'),
                    align='center')]
                    #css=[{'selector': '.row', 'rule': 'margin: 5'}]
                )
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
            map_plot, mappable_events, mappability_text = generate_artist_events_map(events, mbid_entry)
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
    Output('recs-table', 'data'), Output('recs-table', 'columns'),
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
            if (ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks") or ((ctx.triggered[0]['prop_id'] == "mbid-entry-store.children") and (mbid_entry != recs_state_store)):
                return "Clearing recs...", None, None, None, None
            elif (ctx.triggered[0]['prop_id'] == "query-venues-store.data"):
                query_events_list = json.loads(events_json)

                events_list = get_events_list(query_events_list)
                events_df = pd.DataFrame(events_list)
                recs = gen.get_basic_artist_rec_from_df(events_df, mbid_entry, with_geo=False)
                if recs is None:
                    return "No events found for {} between {} and {}".format(mbid_entry, START_DATE, END_DATE), None, None, mbid_entry, events_list
                else:
                    #recs_table = generate_table(recs, len(recs))
                    recs_table = recs.to_dict('records')
                    recs_columns = [{"name": i, "id": i} for i in recs.columns if i != 'id']
                    return "Got recs for {}".format(mbid_entry), recs_table, recs_columns, mbid_entry, events_list
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
    [Input('recs-table', 'active_cell')],
    [State('venue-event-storage', 'data'), State('recs-table', 'data')])
def display_recommended_artist_info(active_cell, events_list, recs_table_data):
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