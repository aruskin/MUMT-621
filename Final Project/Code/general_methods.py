import networkx as nx
import pandas as pd
import plotly.graph_objects as go

# Return list of artists with the most overlapping venues as query artist
# (Doesn't take into account how often they've played at these venues,
# whether they've shared bill with query artist, etc.)
# Assume bipartite graph of artist-venue data
def get_basic_artist_rec_from_bigraph(bi_G, query_id, n_recs=10):
  venues, artists = nx.bipartite.sets(bi_G)
  venue_degrees, artist_degrees = nx.bipartite.degrees(bi_G, artists)
  artists_ranked = [(k, v) for k, v in sorted(artist_degrees, key=lambda item: item[1], reverse=True) \
                    if k != query_id]
  num_venues = len(venues)
  outlist = artists_ranked[:n_recs]
  outlist = [(bi_G.nodes[x]['name'], y) for x, y in outlist]
  df = pd.DataFrame(outlist)
  df = df.rename(columns={0:"Artist", 1:"Shared Venues"})
  return df

def plot_network(G, mbid, bipartite=False):
  seed_artist = G.nodes[mbid]['name']

  # Some things should prob differ depending on type of graph, but still figuring that out
  if bipartite:
    plot_title = "<br>Artist-venue graph for {}".format(seed_artist)  
  else:
    plot_title = "<br>Artist-event-venue graph for {}".format(seed_artist)  
  
  pos = nx.layout.spring_layout(G)

  for node in G.nodes:
    G.nodes[node]['pos'] = list(pos[node])

  edge_x = []
  edge_y = []
  for edge in G.edges():
      x0, y0 = G.nodes[edge[0]]['pos']
      x1, y1 = G.nodes[edge[1]]['pos']
      edge_x.append(x0)
      edge_x.append(x1)
      edge_x.append(None)
      edge_y.append(y0)
      edge_y.append(y1)
      edge_y.append(None)

  edge_trace = go.Scatter(
      x=edge_x, y=edge_y,
      line=dict(width=0.5, color='#888'),
      hoverinfo='none',
      mode='lines')

  node_x = []
  node_y = []
  node_text = []
  node_types = []
  bipartite_node_coloring = []
  for node in G.nodes():
      x, y = G.nodes[node]['pos']
      node_x.append(x)
      node_y.append(y)
      # Every node should have some human readable info associated with it
      text = G.nodes[node]['name'] + "<br>Type: {}".format(G.nodes[node]['node_type'])
      if 'date' in G.nodes[node].keys():
          text = text + "<br>Date: {}".format(G.nodes[node]['date'])
      if node == mbid:
        node_types.append('Seed')
        bipartite_node_coloring.append(G.degree(node))
      else:
        node_types.append(G.nodes[node]['node_type'])
        if bipartite:
          if G.nodes[node]['node_type'] == "Artist":
            node_degree = G.degree(node)
            bipartite_node_coloring.append(node_degree)
            text = text + "<br>Shared venues: {}".format(node_degree)
          else:
            bipartite_node_coloring.append(0)
      node_text.append(text)
  
  # Set node colors based on type (Seed, Artist, Venue, Event)
  if bipartite:
    node_colors = bipartite_node_coloring
  else:
    node_types, node_colors = np.unique(node_types, return_inverse=True)

  node_trace = go.Scatter(
      x=node_x, y=node_y, text=node_text,
      mode='markers',
      hoverinfo='text',
      marker=dict(
          showscale=False,
          colorscale='YlGnBu',
          reversescale=True,
          color=node_colors,
          size=10
          ),
          line_width=2)

  fig = go.Figure(data=[edge_trace, node_trace],
             layout=go.Layout(
                title=plot_title,
                titlefont_size=16,
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20,l=5,r=5,t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                )
  return fig