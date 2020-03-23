import dash
import dash_core_components as dcc
import dash_html_components as html
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
START_DATE = datetime.datetime.strptime('2015-01-01', '%Y-%m-%d')
END_DATE = datetime.datetime.today()

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

  G = nx.Graph()   #initialize graph
  mb.add_mb_events_to_bipartite_graph(test_mb_events, G)

  # pull all other events held at same venue +/- two years of seed artist's event
  # add events, artists to graph
  venue_event_dict = {}
  for event in test_mb_events:
    event_date = mb.try_parsing_mb_date(event['life-span']['begin'])
    if (event_date >= mb.START_DATE) & (event_date <= mb.END_DATE):
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
    return recs

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

#########

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.layout = html.Div([
    html.H1(
        children='Get Artist Recommendations by Tour History',
        style={
            'textAlign': 'center'
        }
    ),
    html.Label("Enter artist's MusicBrainz ID:"),
    dcc.Input(id='mbid-input', value='50eec634-7c42-41ee-9b1f-b41d9ca28b26', 
     type='text'),
    html.Button(id='mbid-submit-button', children='Submit'),
     # Hidden div inside the app that stores the intermediate value
    html.Div(id='mbid-entry-store', style={'display': 'none'}), 
    html.Div(id='mbid-valid-store', style={'display': 'none'}),
    html.Div(id='mbid-message'),
    html.Div(id='store-query-mbid', style={'display': 'none'}),
    html.Button(id='get-recs-button', children='Find Related Artists'),
    html.Div(id='get-recs-output'),
    html.Table(id='recs-table')
    #html.H4(children='US Agriculture Exports (2011)')
    #generate_table(df)
])

@app.callback(
    [Output('mbid-entry-store', 'children'), Output('mbid-valid-store', 'children'), \
     Output('mbid-message', 'children')],
    [Input('mbid-submit-button', 'n_clicks')],
              [State('mbid-input', 'value')]
    )
def update_mbid_outputs(n_clicks, mbid_input_value):
    if n_clicks is None:
        raise PreventUpdate
    else:
        try:
            result = musicbrainzngs.get_artist_by_id(mbid_input_value)
        except musicbrainzngs.WebServiceError as exc:
            message = "Something went wrong with the request: %s" % exc
            return mbid_input_value, False, message
        else:
            artist = result["artist"]
            message = "Query artist is: {}".format(artist["name"])
            return mbid_input_value, True, message

@app.callback(
    [Output('get-recs-output', 'children'), Output('recs-table', 'children')],
    [Input('mbid-submit-button', 'n_clicks'), Input('get-recs-button', 'n_clicks')],
    [State('mbid-valid-store', 'children'), State('mbid-entry-store', 'children')]
    )
def update_recs_output(mbid_submit, recs_submit, mbid_valid, mbid_entry):
    if (mbid_submit is None) or (recs_submit is None):
        raise PreventUpdate
    else:
        if mbid_valid:
            recs = get_artist_recs(mbid_entry)
            recs_table = generate_table(recs, len(recs))
            return "Getting recs for {}".format(mbid_entry), recs_table
        else:
            return "Need to enter valid MBID", None

if __name__ == '__main__':
    app.run_server(debug=True)