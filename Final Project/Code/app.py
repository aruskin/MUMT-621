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
        dcc.Store(id='mbid-entry-store'),
        dcc.Store(id='query-venues-store'),
        html.Div(id='recs-state-store', style=TOGGLE_OFF),
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
            style=TOGGLE_OFF),
    html.Div(id='mbid-message'),
    html.Br(),
    dbc.Button(id='get-recs-button', children='Find Related Artists', style=TOGGLE_OFF)
]

recs_output = html.Div(id='get-recs-container',
    children=[
        dbc.Row(dbc.Spinner(html.Div(id='get-recs-spinner1'), color="primary")),
        dbc.Row(dbc.Spinner(html.Div(id='get-recs-spinner2'), color="secondary")),
        dbc.Row(html.H3("Top 10 Artists by Number of Shared Venues")),
        dbc.Row([
            dbc.Col(dash_table.DataTable(id='recs-table', 
                columns=[{"name": i, "id": i} for i in REC_COLUMNS]), 
            id='recs-table-container', align='center'),
            dbc.Tooltip("Click on a cell for more information!",
                target='recs-table-container')
        ])
    ],
    style=TOGGLE_OFF)

card_body_style = {'maxHeight':'150px', 'overflowY':'scroll'}

summary_cards = [
    dbc.Col(dbc.Card([
                dbc.CardHeader("Summary"), 
                dbc.CardBody(id='query-events-text', style=card_body_style)
        ])),
    dbc.Col(dbc.Card([
                dbc.CardHeader("Mappability"), 
                dbc.CardBody(id='query-map-text', style=card_body_style)
        ]))
    ]

more_info_card = [dbc.Card([
                    dbc.CardHeader("More info about recommendations"), 
                    dbc.CardBody(id='rec-select-text', style=card_body_style), 
                    dbc.CardLink(id='rec-select-mb-link')],
                id='more-info-card',
                style=TOGGLE_OFF)]

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
        # 1st column: User input stuff & recs output table
        dbc.Col([
            dbc.Row(dbc.Col(user_inputs)),
            dbc.Row(dbc.Col(recs_output)),
            dbc.Row(dbc.Col(more_info_card))
        ], width=4),
        # 2nd column: summary of info about query artist & map
        dbc.Col([
            dbc.Row(summary_cards),
            dbc.Row(map_component),
            dbc.Row([html.H3(id='venue-events-heading')]),
            dbc.Row([dbc.Table(id='venue-events-table', striped=True, size='sm')], 
                style={'maxHeight': '250px','overflowY':'scroll'})
            ], width=8)
        ])
    ], fluid=True)

###############
# Callbacks!

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
        if artist_input_value == "":
            message = "Please enter an artist name"
            return message, []
        else:
            try:
                result = musicbrainzngs.search_artists(artist=artist_input_value)
            except musicbrainzngs.WebServiceError as exc:
                message = "Something went wrong with the request: %s" % exc
                return message, []
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
            return TOGGLE_OFF
        else:
            return TOGGLE_ON

# When user selects option from dropdown list, update hidden elements for storing
# query MBID and toggle visibility of Find Related Artists button
@app.callback(
    [Output('mbid-entry-store', 'data'), Output('get-recs-button', 'style')],
    [Input('mbid-submit-button', 'n_clicks'), Input('artist-dropdown', 'value')],
    [State('artist-dropdown', 'options')])
def update_mbid_outputs(mbid_submit, artist_dropdown_selection, artist_dropdown_options):
    ctx = dash.callback_context
    if ctx.triggered:
        # If user hits Submit button, clear out entry store and hide Find Related Artists button
        if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks":
            return None, TOGGLE_OFF
        else:
            selected = [x['label'] for x in artist_dropdown_options \
                if x['value'] == artist_dropdown_selection]
            mbid_store_dict = dict(mbid=artist_dropdown_selection, name=selected[0])
            mbid_store_data = json.dumps(mbid_store_dict)
            return mbid_store_data, TOGGLE_ON
    else:
        raise PreventUpdate

# Toggling visibility of section with spinners and recommendation table - hide when Submit button 
# clicked, show when Find Related Artists button clicked
@app.callback(
    Output('get-recs-container', 'style'),
    [Input('mbid-submit-button', 'n_clicks'), Input('get-recs-button', 'n_clicks')]
    )
def toggle_rec_area_visibility(mbid_submit, recs_submit):
    ctx = dash.callback_context
    if ctx.triggered:
        if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks":
            return TOGGLE_OFF
        else:
            return TOGGLE_ON
    else:
        raise PreventUpdate

# Updating top spinner, data store for query artist events list, summaries of initial event pull and
# mappability, and points to plot on map
# Add data when events pulled (Find Related Artists button clicked), 
# clear data when user searches for new artist (Submit button clicked)
@app.callback(
    [Output('get-recs-spinner1', 'children'), 
    Output('query-venues-store', 'data'), Output('query-events-text', 'children'), 
    Output('query-map-text', 'children'), Output('artist-venue-map', 'figure')],
    [Input('mbid-submit-button', 'n_clicks'), Input('get-recs-button', 'n_clicks')],
    [State('mbid-entry-store', 'data')]
)
def update_summary_text(mbid_submit, recs_submit, mbid_entry_store):
    ctx = dash.callback_context
    if ctx.triggered:
        if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks":
            return None, None, None, None, default_map_figure
        else:
            mbid_entry_dict = json.loads(mbid_entry_store)
            mbid_entry = mbid_entry_dict['mbid']
            artist_name = mbid_entry_dict['name']
            events, message = gen.get_mb_and_sl_events(mbid_entry, \
                MB_EVENT_PULLER, SL_EVENT_PULLER, VENUE_MAPPER,\
                START_DATE, END_DATE, sl_page_limit=SL_ARTIST_PAGE_LIMIT)
            event_count = len(events)
            venue_count = 0
            mappable_events = 0
            events_json = json.dumps([])
            map_plot = default_map_figure

            if event_count > 0:
                venue_list = []
                for event in events:
                    if event.venue not in venue_list:
                        venue_list.append(event.venue)
                        venue_count += 1
                serializable_events = [event.to_dict() for event in events]
                events_json = json.dumps(serializable_events, default=str)
                map_plot, mappable_events, mappability_text = gen.generate_artist_events_map(events, mbid_entry)
            summary_text = message + " {} events were found at {} unique venues.".format(\
                    event_count, venue_count)
            mappability_message = "{} events mapped.".format(mappable_events)
            if mappable_events < event_count:
                mappability_message = mappability_message +" No coordinates found for {}.".format(mappability_text)
            return "Pulled events for {}".format(artist_name), events_json, summary_text, mappability_message, map_plot
    else:
        raise PreventUpdate 

# When user hits "Find Related Artists", generate list of recommendations based on
# query artist (need to have a valid MBID stored) and display in table
@app.callback(
    [Output('get-recs-spinner2', 'children'), 
    Output('recs-table', 'data'), Output('recs-table', 'active_cell'), Output('recs-table', 'selected_cells'),
    Output('recs-state-store', 'children'), Output('venue-event-storage', 'data'),
    Output('map-tooltip', 'style')],
    [Input('query-venues-store', 'data'), Input('mbid-entry-store', 'data'), 
    Input('mbid-submit-button', 'n_clicks')],
    [State('recs-state-store', 'children'), State('recs-table', 'active_cell'), State('recs-table', 'selected_cells')]
    )
def update_recs_output(events_json, mbid_entry_store, submit_clicks, recs_state_store, active_cell, selected_cell):
    ctx = dash.callback_context

    if ctx.triggered:
        if mbid_entry_store:
            mbid_entry_dict = json.loads(mbid_entry_store)
            mbid_entry = mbid_entry_dict['mbid']
            artist_name = mbid_entry_dict['name']
        else:
            mbid_entry = None

        if active_cell:
            deactivated_cell = dict(row=-1, column=-1, column_id=None, row_id=None)
        else:
            deactivated_cell = None

        trigger = ctx.triggered[0]['prop_id']
        if (trigger == "query-venues-store.data") and events_json:
            query_events_list = json.loads(events_json)

            events_list = gen.get_events_list(\
                query_events_list, MB_EVENT_PULLER, SL_EVENT_PULLER, VENUE_MAPPER, \
                START_DATE, END_DATE, SL_VENUE_PAGE_LIMIT)
            if len(events_list) > 0:
                events_df = pd.DataFrame(events_list)
                recs = gen.get_basic_artist_rec_from_df(events_df, mbid_entry)
                recs_table = recs.to_dict('records')
                message = "Got recommendations for {}".format(artist_name)
                toggle = TOGGLE_ON
            else:
                message = "No events found for {} between {} and {}, so no recommendations.".format(\
                    artist_name, START_DATE, END_DATE)
                recs_table = [{}]
                toggle = TOGGLE_OFF
            return message, recs_table, deactivated_cell, [], mbid_entry, events_list, toggle
        elif (trigger == "mbid-entry-store.data") and (mbid_entry == recs_state_store):
            raise PreventUpdate
        else:
            #print("here?: {}".format(ctx.triggered[0]['prop_id']))
            message = ""
            return message, [{}], deactivated_cell, [], None, None, TOGGLE_OFF
    else:
        raise PreventUpdate

@app.callback(
    [Output('venue-events-table', 'children'), Output('venue-events-heading', 'children')],
    [Input('mbid-submit-button', 'n_clicks'), Input('artist-venue-map', 'clickData')],
    [State('venue-event-storage', 'data')])
def update_venue_events_on_click(mbid_submit, selected_data, events_list):
    ctx = dash.callback_context
    if ctx.triggered:
        if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks":
            return None, ""
        else:
            if events_list is None:
                raise PreventUpdate
            else:
                chosen = [point["customdata"] for point in selected_data["points"]]
                venue_name, venue_id = chosen[0]

                events_df = pd.DataFrame(events_list)
                events_df['venue_mbid'] = events_df['venue_mbid'].fillna('')
                events_df['venue_slid'] = events_df['venue_slid'].fillna('')
                events_df['venue_id'] = list(zip(events_df.venue_mbid, events_df.venue_slid))
                events_df['event_date'] = events_df['time'].apply(lambda x:str(x))
                events_df['link'] = list(zip(events_df.event_slurl.combine_first(events_df.event_mburl),\
                 events_df['event_slurl'].apply(lambda x: 'Setlist.fm page' if x else 'MusicBrainz page')))
                events_df['Link to Event Page'] = events_df['link'].apply(lambda x: html.A(x[1], href=x[0], target='_blank'))
                selected = events_df[events_df['venue_id'] == tuple(venue_id)]
                events_table = generate_table(selected[['event_date', 'artist_name', 'Link to Event Page']], len(selected))
                heading_text = 'Who else played {venue} between {start_date} and {end_date}?'.format(\
                    venue=venue_name, start_date=START_DATE, end_date=END_DATE)
                return events_table, heading_text

@app.callback([Output('more-info-card', 'style'), 
    Output('rec-select-text', 'children'), 
    Output('rec-select-mb-link', 'children'), Output('rec-select-mb-link', 'href')],
    [Input('mbid-submit-button', 'n_clicks'), Input('recs-table', 'active_cell')],
    [State('venue-event-storage', 'data'), State('recs-table', 'data'), 
    State('mbid-entry-store', 'data')])
def display_recommended_artist_info(mbid_submit, active_cell, events_list, recs_table_data, mbid_store):
    ctx = dash.callback_context
    card_display_out = TOGGLE_OFF
    card_text_out = ""
    mb_link_text_out = ""
    mb_link_url_out = ""
    if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks": #hide and clear on Submit
        return card_display_out, card_text_out, mb_link_text_out, mb_link_url_out
    else:
        if active_cell is None:
            raise PreventUpdate
        elif 'row_id' not in active_cell: #selecting cell in empty table
            return card_display_out, card_text_out, mb_link_text_out, mb_link_url_out
        elif active_cell['row_id'] is None:
            return card_display_out, card_text_out, mb_link_text_out, mb_link_url_out
        else:
            active_row_id = active_cell['row_id']
            active_col_id = active_cell['column_id']
            selected_record = [x for x in recs_table_data if x['id']==active_row_id][0]
            cell_artist = selected_record['Artist']
            artist_mbid = selected_record['id']
            shared_venues = selected_record['Shared Venues']

            mbid_entry_dict = json.loads(mbid_store)
            query_artist = mbid_entry_dict['name']

            card_display_out = TOGGLE_ON

            if active_col_id == 'Artist':
                artist_info = gen.get_more_artist_info(artist_mbid)
                message = []
                if artist_info['area']:
                    message.append(html.P('Area: {}'.format(artist_info['area'])))
                if artist_info['life_span']:
                    message.append(html.P('Lifespan: {}'.format(artist_info['life_span'])))
                if len(artist_info['top_tags']) > 0:
                    message.append(html.P('Top tags on MusicBrainz: {}'.format(', '.join(artist_info['top_tags']))))
                message.append(html.P(['Find out more at ', 
                    html.A("{}'s MusicBrainz artist page".format(cell_artist),
                        href='https://musicbrainz.org/artist/' + artist_mbid,
                        target='_blank')]))
                card_text_out = html.Div(message)
                return card_display_out, card_text_out, mb_link_text_out, mb_link_url_out
            else: #if active_col_id == 'Shared Venues' -- only other option
                relevant_events = [event for event in events_list if \
                    event['artist_mbid'] == artist_mbid]
                event_text = [html.A("{venue} ({date}), ".format(date=str(x['time']), venue=gen.not_none(x['venue_slname'], x['venue_mbname'])),
                    href=gen.not_none(x['event_slurl'], x['event_mburl']), target="_blank") \
                    for x in relevant_events]
                message = '{} and {} have recently played at {} of the same venues.'.format(\
                    cell_artist, query_artist, shared_venues)
                message = message + " {}'s events: ".format(cell_artist)
                card_text_out = html.P([message] + event_text)
                
            return card_display_out, card_text_out, mb_link_text_out, mb_link_url_out

if __name__ == '__main__':
    app.run_server(debug=True)