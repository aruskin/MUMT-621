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

recs_output = html.Div(id='spinners-container',
    children=[
        dbc.Row(dbc.Spinner(html.Div(id='get-recs-spinner1'), color="primary")),
        dbc.Row(dbc.Spinner(html.Div(id='get-recs-spinner2'), color="secondary")),
    ],
    style=TOGGLE_OFF)

recs_table = html.Div(id='recs-table-outer-container',
    children=[
        html.Div(id='recs-table-inner-container', 
            children=[
                dbc.Row(html.H3("Top 10 Artists by Number of Shared Venues")),
                dbc.Row(dbc.Col(dash_table.DataTable(id='recs-table', 
                    columns=[{"name": i, "id": i} for i in REC_COLUMNS]),
                align='center'))
            ]),
        dbc.Tooltip("Click on a cell for more information!",
            target='recs-table-inner-container')
        ],
    style=TOGGLE_OFF)

card_body_style = {'maxHeight':'150px', 'overflowY':'scroll'}

summary_cards = [
    dbc.Col(dbc.Card([
                dbc.CardHeader("Summary"), 
                dbc.CardBody(id='query-events-text', style=card_body_style)
        ]))
    ]

more_info_card = [dbc.Card([
                    dbc.CardHeader("More info about recommendations"), 
                    dbc.CardBody(id='rec-select-text', style=card_body_style)],
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
            dbc.Row(dbc.Col(recs_table)),
            dbc.Row(html.Br()),
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
    [Output('mbid-message', 'children'), Output('artist-dropdown', 'options'),
    Output('artist-dropdown', 'value')],
    [Input('mbid-submit-button', 'n_clicks')],
    [State('artist-input', 'value')])
def update_artist_dropdown(n_clicks, artist_input_value):
    if n_clicks is None:
        raise PreventUpdate
    else:
        if artist_input_value == "":
            message = "Please enter an artist name"
            return message, [], None
        else:
            try:
                result = musicbrainzngs.search_artists(artist=artist_input_value)
            except musicbrainzngs.WebServiceError as exc:
                message = "Something went wrong with the request: %s" % exc
                return message, [], None
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
                return message, options, None

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

@app.callback(
    Output('mbid-entry-store', 'data'),
    [Input('mbid-submit-button', 'n_clicks'), Input('artist-dropdown', 'value')],
    [State('artist-dropdown', 'options')])
def update_mbid_entry_store(mbid_submit, artist_dropdown_selection, artist_dropdown_options):
    if (mbid_submit is None):
        raise PreventUpdate
    else:
        mbid_store_dict = dict(mbid=None, name=None)
        print("MBID submit: {}".format(mbid_submit))
        print("Artist dropdown selection: {}".format(artist_dropdown_selection))
        if artist_dropdown_selection:
            selected = [x['label'] for x in artist_dropdown_options \
                if x['value'] == artist_dropdown_selection]
            mbid_store_dict['mbid'] = artist_dropdown_selection
            mbid_store_dict['name'] = selected[0]
        mbid_store_data = json.dumps(mbid_store_dict)
        print(mbid_store_data)
        return mbid_store_data

@app.callback(
    Output('get-recs-button', 'style'),
    [Input('mbid-submit-button', 'n_clicks'), Input('artist-dropdown', 'value')])
def toggle_recs_button_visibility(mbid_submit, artist_dropdown_selection):
    if (mbid_submit is None):
        raise PreventUpdate
    else:
        toggle = TOGGLE_OFF
        if artist_dropdown_selection:
            toggle = TOGGLE_ON
        return toggle

# # When user selects option from dropdown list, update hidden elements for storing
# # query MBID and toggle visibility of Find Related Artists button
# @app.callback(
#     [Output('mbid-entry-store', 'data'), Output('get-recs-button', 'style')],
#     [Input('mbid-submit-button', 'n_clicks'), Input('artist-dropdown', 'value')],
#     [State('artist-dropdown', 'options')])
# def update_mbid_outputs(mbid_submit, artist_dropdown_selection, artist_dropdown_options):
#     if (mbid_submit is None):
#         raise PreventUpdate
#     else:
#         mbid_store_dict = dict(mbid=None, name=None)
#         toggle = TOGGLE_OFF
#         if artist_dropdown_selection:
#             selected = [x['label'] for x in artist_dropdown_options \
#                 if x['value'] == artist_dropdown_selection]
#             mbid_store_dict['mbid'] = artist_dropdown_selection
#             mbid_store_dict['name'] = selected[0]
#             toggle = TOGGLE_ON
#         mbid_store_data = json.dumps(mbid_store_dict)
#         return mbid_store_data, toggle

# Toggling visibility of section with spinners and recommendation table - hide when Submit button 
# clicked, show when Find Related Artists button clicked
@app.callback(
    Output('spinners-container', 'style'),
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


@app.callback(
    Output('artist-venue-map', 'clickData'),
    [Input('get-recs-button', 'n_clicks'), Input('mbid-submit-button', 'n_clicks')]
    )
def clear_map_click_data(recs_submit, mbid_submit):
    if recs_submit is None: 
        raise PreventUpdate
    else:
        click_data_out = {'points':[], 'customdata':[]}
        return click_data_out

# Updating top spinner, data store for query artist events list, summaries of initial event pull and
# mappability, and points to plot on map
# Add data when events pulled (Find Related Artists button clicked), 
# clear data when user searches for new artist (Submit button clicked)
@app.callback(
    [Output('get-recs-spinner1', 'children'), 
    Output('query-venues-store', 'data'), Output('query-events-text', 'children'), 
    Output('artist-venue-map', 'figure')],
    [Input('get-recs-button', 'n_clicks'), Input('mbid-submit-button', 'n_clicks')],
    [State('mbid-entry-store', 'data'), State('recs-state-store', 'children')]
)
def update_summary_text(recs_submit, mbid_submit, mbid_entry_store, old_recs_state_store):
    if (recs_submit is None) or (mbid_submit is None):
        print("Here 1")
        raise PreventUpdate
    else:
        print("Here 2")
        ctx = dash.callback_context
        trigger = ctx.triggered[0]['prop_id']

        spinner_out = ""
        query_events_data = json.dumps([])
        card_text_out = ""
        map_plot_out = default_map_figure

        print("Trigger: {}".format(trigger))
        print("MBID entry store: {}".format(mbid_entry_store))

        if trigger == 'get-recs-button.n_clicks':
            #if mbid_entry_store:
            mbid_entry_dict = json.loads(mbid_entry_store)
            mbid_entry = mbid_entry_dict['mbid']
            artist_name = mbid_entry_dict['name']
            if mbid_entry:
                if mbid_entry == old_recs_state_store:
                    # user has hit Find Related Artist again button without changing query artist
                    raise PreventUpdate
                else:
                    events, message = gen.get_mb_and_sl_events(mbid_entry, \
                        MB_EVENT_PULLER, SL_EVENT_PULLER, VENUE_MAPPER,\
                        START_DATE, END_DATE, sl_page_limit=SL_ARTIST_PAGE_LIMIT)
                    event_count = len(events)
                    venue_count = 0
                    mappable_events = 0

                    if event_count > 0:
                        venue_list = []
                        for event in events:
                            if event.venue not in venue_list:
                                venue_list.append(event.venue)
                                venue_count += 1
                        serializable_events = [event.to_dict() for event in events]
                        query_events_data  = json.dumps(serializable_events, default=str)
                        map_plot_out, mappable_events, mappability_text = gen.generate_artist_events_map(events, mbid_entry)
                    summary_text = message + " {} events were found at {} unique venues.".format(\
                            event_count, venue_count)
                    mappability_message = "{} events mapped.".format(mappable_events)
                    if mappable_events < event_count:
                        mappability_message = mappability_message +" No coordinates found for {}.".format(mappability_text)
                    card_text_out = html.P([summary_text, html.Hr(), mappability_message])

                    spinner_out = "Pulled events for {}".format(artist_name)
        return spinner_out, query_events_data, card_text_out, map_plot_out

@app.callback(
    [Output('recs-table', 'active_cell'), Output('recs-table', 'selected_cells')],
    [Input('query-venues-store', 'data')]
)
def clear_selected_table_cells(events_json):
    if events_json is None:
        raise PreventUpdate
    else:
        deactivated_cell = dict(row=-1, column=-1, column_id=None, row_id=None)
        selected_cells = []
        return deactivated_cell, selected_cells

# When user hits "Find Related Artists", generate list of recommendations based on
# query artist (need to have a valid MBID stored) and display in table
@app.callback(
    [Output('get-recs-spinner2', 'children'), 
    Output('recs-table', 'data'), 
    Output('recs-state-store', 'children'), Output('venue-event-storage', 'data'),
    Output('map-tooltip', 'style')],
    [Input('query-venues-store', 'data')],
    [State('mbid-entry-store', 'data'), State('recs-state-store', 'children')]
    )
def update_recs_output(events_json, mbid_entry_store, recs_state_store):
    if events_json is None:
        raise PreventUpdate
    else:
        print("Spinner 2: MBID entry store: {}".format(mbid_entry_store))

        mbid_entry_dict = json.loads(mbid_entry_store)
        mbid_entry = mbid_entry_dict['mbid']
        artist_name = mbid_entry_dict['name']
          
        spinner2_message = ""
        recs_table = [{}]
        events_list_out = []
        tooltip_toggle = TOGGLE_OFF

        query_events_list = json.loads(events_json)
        if (len(query_events_list) == 0) and mbid_entry:
            spinner2_message = "No events found for {} between {} and {}, so no recommendations.".format(\
                    artist_name, START_DATE, END_DATE)
        elif len(query_events_list) > 0:
            events_list_out = gen.get_events_list(\
                query_events_list, MB_EVENT_PULLER, SL_EVENT_PULLER, VENUE_MAPPER, \
                START_DATE, END_DATE, SL_VENUE_PAGE_LIMIT)
            if len(events_list_out) > 0:
                events_df = pd.DataFrame(events_list_out)
                recs = gen.get_basic_artist_rec_from_df(events_df, mbid_entry)
                recs_table = recs.to_dict('records')
                spinner2_message = "Got recommendations for {}".format(artist_name)
                tooltip_toggle = TOGGLE_ON
            else:
                spinner2_message = "No events found for {} between {} and {}, so no recommendations.".format(\
                    artist_name, START_DATE, END_DATE)

        return spinner2_message, recs_table, mbid_entry, events_list_out, tooltip_toggle

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
            events_table = []
            heading_text = ""
            if events_list is None:
                raise PreventUpdate
            elif len(events_list) == 0:
                raise PreventUpdate
            else:
                chosen = [point["customdata"] for point in selected_data["points"]]
                if len(chosen) > 0:
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

@app.callback([Output('more-info-card', 'style'), Output('rec-select-text', 'children')],
    [Input('mbid-submit-button', 'n_clicks'), Input('recs-table', 'active_cell')],
    [State('venue-event-storage', 'data'), State('recs-table', 'data'), 
    State('mbid-entry-store', 'data')])
def display_recommended_artist_info(mbid_submit, active_cell, events_list, recs_table_data, mbid_store):
    ctx = dash.callback_context
    card_display_out = TOGGLE_OFF
    card_text_out = ""
    if ctx.triggered[0]['prop_id'] == "mbid-submit-button.n_clicks": #hide and clear on Submit
        return card_display_out, card_text_out
    else:
        if active_cell is None:
            raise PreventUpdate
        elif 'row_id' not in active_cell: #selecting cell in empty table
            return card_display_out, card_text_out
        elif active_cell['row_id'] is None:
            return card_display_out, card_text_out
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
                return card_display_out, card_text_out
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
                
            return card_display_out, card_text_out

@app.callback(
    Output('recs-table-outer-container', 'style'),
    [Input('get-recs-spinner2', 'children')])
def toggle_recs_table_visibility(spinner_2_message):
    if spinner_2_message is None:
        raise PreventUpdate
    else:
        if "Got recommendations" in spinner_2_message:
            return TOGGLE_ON
        else:
            return TOGGLE_OFF

if __name__ == '__main__':
    app.run_server(debug=True)