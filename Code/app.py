import dash
from dash import dcc, html, Input, Output
import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt
import plotly.graph_objs as go
from ipywidgets import widgets, interactive
from IPython.display import display
import datetime

# Load the dataset
file_path = r'C:\Users\deeks\Downloads\merged_dataset_with_updated_clusters_final.csv'
data = pd.read_csv(file_path)

# Ensure 'Date' and 'Time' columns exist
if 'Date' in data.columns and 'Time' in data.columns:
    data['Timestamp'] = pd.to_datetime(data['Date'] + ' ' + data['Time'])
else:
    raise ValueError("The dataset must contain 'Date' and 'Time' columns.")

# Define actions to ignore
actions_to_ignore = ["---", "SRV_NET -", "joined network", "left network", "getdatabase"]
ignore_prefixes = ["NETCREATE APPSERVER", "SRV_NET"]

# Filter out unwanted actions
data = data[~data['Action'].isin(actions_to_ignore) & ~data['Action'].str.startswith(tuple(ignore_prefixes))]

# Filter actions related to editing and commenting
edit_actions = data[data['Action'].str.contains('edit', case=False, na=False)]
edit_counts = edit_actions.groupby(['DataID', 'Action']).size().reset_index(name='EditCount')

comment_actions = data[data['Action'].str.contains('comment', case=False, na=False)]
comment_actions.loc[:, 'DataDetail'] = comment_actions['DataDetail'].fillna('')

# More processing for additional visualizations...
# Example for merged actions based on time proximity
merged_actions = pd.merge_asof(
    comment_actions.sort_values('Timestamp'),
    edit_actions.sort_values('Timestamp'),
    on='Timestamp',
    by='DataID',
    tolerance=pd.Timedelta('5D'),
    direction='forward'
)
responses = merged_actions.dropna(subset=['Action_y'])

# Group by node (DataID) and user (Addr) to find comments
comment_counts = comment_actions.groupby(['DataID', 'Addr']).agg({'Action': 'count', 'DataDetail': lambda x: ', '.join(x.astype(str))}).reset_index()
comment_counts.columns = ['NodeID', 'User', 'CommentCount', 'Comments']

# Group by user (Addr) to find most active commenters
most_active_commenters = comment_actions.groupby('Addr').agg({'Action': 'count', 'DataDetail': lambda x: ', '.join(x.astype(str))}).reset_index()
most_active_commenters.columns = ['User', 'CommentCount', 'Comments']

# Group by node (DataID) to find most commented nodes
most_commented_nodes = comment_actions.groupby('DataID').agg({'Action': 'count', 'DataDetail': lambda x: ', '.join(x.astype(str))}).reset_index()
most_commented_nodes.columns = ['NodeID', 'CommentCount', 'Comments']

# Group by timestamp to find comment trends over time
comment_trends = comment_actions.groupby('Timestamp').agg({'Action': 'count', 'DataDetail': lambda x: ', '.join(x.astype(str))}).reset_index()
comment_trends.columns = ['Timestamp', 'CommentCount', 'Comments']

# Create transitions between actions for each user
data['NextAction'] = data.groupby('Addr')['Action'].shift(-1)
transitions = data.dropna(subset=['NextAction'])
transitions = transitions.groupby(['Action', 'NextAction']).size().reset_index(name='count')

# Group actions for timeline chart
grouped_actions = data.groupby(['Timestamp', 'DataID', 'Action', 'Addr']).size().reset_index(name='Count')

# Initialize the Dash app
app = dash.Dash(__name__)

# Layout of the app
app.layout = html.Div([
    html.H1("User Activity Dashboard", style={'text-align': 'center'}),

    # Filters
    html.Div([
        html.Label('Select Network:', style={'font-weight': 'bold'}),
        dcc.Dropdown(
            id='network-dropdown',
            options=[{'label': 'ALL', 'value': 'ALL'}] + [{'label': i, 'value': i} for i in sorted(data['NetName'].unique())],
            value='ALL',
            clearable=False,
        ),
        html.Label('Select Cluster:', style={'font-weight': 'bold'}),
        dcc.Dropdown(
            id='cluster-dropdown',
            options=[{'label': 'ALL', 'value': 'ALL'}] + [{'label': i, 'value': i} for i in sorted(data['Cluster_y'].unique())],
            value='ALL',
            clearable=False,
        ),
        html.Label('Select User:', style={'font-weight': 'bold'}),
        dcc.Dropdown(
            id='user-dropdown',
            options=[{'label': 'ALL', 'value': 'ALL'}] + [{'label': i, 'value': i} for i in sorted(data['Addr'].unique())],
            value='ALL',
            clearable=False,
        ),
        html.Label('Select Date Range:', style={'font-weight': 'bold'}),
        dcc.DatePickerRange(
            id='date-picker',
            start_date=min(data['Timestamp']),
            end_date=max(data['Timestamp']),
            display_format='YYYY-MM-DD'
        ),
    ]),

    # Graphs
    html.Div([
        dcc.Graph(id='activity-spikes-graph'),
        html.H3("1. What sequence of activities did each individual network foster?"),
        dcc.Graph(id='individual-network-sequence-graph'),
        html.H3("3. What sequence of activities did each unique group engage in?"),
        dcc.Graph(id='group-sequence-graph'),
        html.H3("4. Were there spikes in activity for either group?"),
        dcc.Graph(id='spikes-graph'),
        html.H3("5. When did groups either edit or comment on each other's nodes?"),
        dcc.Graph(id='edit-comment-timeline'),
        html.H3("6. Which nodes received the most editing?"),
        dcc.Graph(id='most-edited-nodes-graph'),
        html.H3("7. Which user/group was most active?"),
        dcc.Graph(id='most-active-user-graph'),
        dcc.Graph(id='activity-graph'),
        dcc.Graph(id='active-users'),
        dcc.Graph(id='heatmap'),
        dcc.Graph(id='pie-chart'),
        dcc.Graph(id='line-chart'),
        dcc.Graph(id='comments-per-node'),
        dcc.Graph(id='most-active-commenters'),
        dcc.Graph(id='comment-trends-over-time'),
        dcc.Graph(id='comments-edits-timeline'),
        dcc.Graph(id='comments-response-analysis'),
        dcc.Graph(id='user-contribution-graph'),
        html.H3("Flow of User Activities"),
        dcc.Graph(id='user-activity-sankey'),
    ]),
])

# Callback to update the graphs based on filters
@app.callback(
    [Output('activity-spikes-graph', 'figure'),
     Output('individual-network-sequence-graph', 'figure'),
     Output('group-sequence-graph', 'figure'),
     Output('spikes-graph', 'figure'),
     Output('edit-comment-timeline', 'figure'),
     Output('most-edited-nodes-graph', 'figure'),
     Output('most-active-user-graph', 'figure'),
     Output('activity-graph', 'figure'),
     Output('active-users', 'figure'),
     Output('heatmap', 'figure'),
     Output('pie-chart', 'figure'),
     Output('line-chart', 'figure'),
     Output('comments-per-node', 'figure'),
     Output('most-active-commenters', 'figure'),
     Output('comment-trends-over-time', 'figure'),
     Output('user-contribution-graph', 'figure'),
     Output('user-activity-sankey', 'figure')],
    [Input('network-dropdown', 'value'),
     Input('cluster-dropdown', 'value'),
     Input('user-dropdown', 'value'),
     Input('date-picker', 'start_date'),
     Input('date-picker', 'end_date')]
)
def update_graphs(selected_network, selected_cluster, selected_user, start_date, end_date):
    # Filter data based on selections
    filtered_data = data[(data['Timestamp'] >= start_date) & (data['Timestamp'] <= end_date)]

    if selected_network != 'ALL':
        filtered_data = filtered_data[filtered_data['NetName'] == selected_network]

    if selected_cluster != 'ALL':
        filtered_data = filtered_data[filtered_data['Cluster_y'] == selected_cluster]

    if selected_user != 'ALL':
        filtered_data = filtered_data[filtered_data['Addr'] == selected_user]

    # Spikes in activity
    time_series_data = filtered_data.set_index('Timestamp').groupby([pd.Grouper(freq='H'), 'Action']).size().unstack(fill_value=0)
    fig_spikes = go.Figure()
    for col in time_series_data.columns:
        fig_spikes.add_trace(go.Scatter(x=time_series_data.index, y=time_series_data[col], mode='lines', name=col))
    fig_spikes.update_layout(title="Spikes in Activity Over Time", xaxis_title='Time', yaxis_title='Transaction Count', hovermode='x unified')

    # Individual network sequence graph
    individual_sequence_df = filtered_data.groupby(['NetName', 'Action']).size().reset_index(name='count')
    individual_sequence_fig = px.bar(individual_sequence_df, x='Action', y='count', color='NetName', title='Sequence of Activities per Individual Network')

    # Group sequence graph
    grouped_df_filtered = filtered_data.groupby(['Cluster_y', 'Action']).size().reset_index(name='count')
    group_sequence_fig = px.bar(grouped_df_filtered, x='Action', y='count', color='Cluster_y', title='Sequence of Activities per Group')

    # Spikes graph
    filtered_data['Date'] = pd.to_datetime(filtered_data['Date'])
    action_over_time_filtered = filtered_data.groupby(['Date', 'Cluster_y']).size().reset_index(name='count')
    spikes_fig = px.line(action_over_time_filtered, x='Date', y='count', color='Cluster_y', title='Spikes in Activity per Group Over Time')
    spikes_fig.update_layout(xaxis=dict(tickformat="%Y-%m-%d"))

    # Timeline chart of edit and comment actions
    timeline_fig = px.scatter(grouped_actions, x='Timestamp', y='DataID', color='Action', symbol='Addr', size='Count',
                              title='Timeline of Edit and Comment Actions',
                              labels={'DataID': 'Node (DataID)', 'Addr': 'User', 'Timestamp': 'Time'})
    timeline_fig.update_traces(marker=dict(line=dict(width=2, color='DarkSlateGrey')))

    # Most edited nodes graph
    most_edited_nodes_fig = px.bar(edit_counts, x='DataID', y='EditCount', color='Action', title='Edit Counts by Node (DataID) and Action')

    # Most active user graph
    most_active_user_fig = px.histogram(filtered_data, x='Addr', color='Cluster_y', title='Most Active Users per Cluster')

    # General activity over time
    activity_fig = px.scatter(filtered_data, x='Timestamp', y='Action', color='NetName',
                              hover_data=['NetName', 'Addr', 'DataDetail', 'Action'],
                              labels={'Timestamp': 'Time', 'Action': 'Activity Type'},
                              title='General Network Activities Over Time')

    # Most active users
    active_users = filtered_data['Addr'].value_counts().nlargest(10).reset_index()
    active_users.columns = ['User', 'Count']
    active_users_fig = px.bar(active_users, x='User', y='Count', title='Top 10 Active Users overall')

    # Heatmap of user activity
    heatmap_fig = px.density_heatmap(filtered_data, x='Timestamp', y='Addr', title='Heatmap of User Activity')

    # Pie chart of actions distribution
    actions_distribution = filtered_data.groupby(['Action', 'Addr']).size().reset_index(name='Count')
    total_count = actions_distribution['Count'].sum()
    actions_distribution['Percentage'] = (actions_distribution['Count'] / total_count) * 100
    pie_chart_fig = px.sunburst(actions_distribution, path=['Action', 'Addr'], values='Count',
                                title="Distribution of Actions",
                                hover_data={'Count': True, 'Percentage': True})
    pie_chart_fig.update_traces(hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{customdata[1]:.2f}%')

    # Line chart of user activity over time
    line_chart_fig = px.line(filtered_data, x='Timestamp', y='Action', color='Addr', title='User Activity Over Time')

    # Stacked bar chart of most commented nodes by user
    stacked_bar_fig = px.bar(comment_counts, x='NodeID', y='CommentCount', color='User', title='Comments per Node by User',
                             hover_data={'Comments': True})

    # Bar chart of most active commenters
    active_commenters_fig = px.bar(most_active_commenters, x='User', y='CommentCount', title='Most Active Commenters',
                                   hover_data={'Comments': True})

    # Line chart of comment trends over time
    comment_trends_fig = px.line(comment_trends, x='Timestamp', y='CommentCount', title='Comment Trends Over Time',
                                 hover_data={'Comments': True})

    # User contribution network
    contribution_data = filtered_data.groupby(['Addr', 'Action']).size().reset_index(name='Count')
    fig_user_contribution = px.scatter(contribution_data, x='Addr', y='Action', size='Count', color='Addr', title="User Contribution Network")

    # Create transitions between actions for each user
    filtered_data['NextAction'] = filtered_data.groupby('Addr')['Action'].shift(-1)
    transitions_filtered = filtered_data.dropna(subset=['NextAction'])
    transitions_filtered = transitions_filtered.groupby(['Action', 'NextAction']).size().reset_index(name='count')

    # Prepare data for Sankey diagram
    all_actions = pd.concat([transitions_filtered['Action'], transitions_filtered['NextAction']]).unique()
    action_indices = {action: idx for idx, action in enumerate(all_actions)}

    sources = [action_indices[action] for action in transitions_filtered['Action']]
    targets = [action_indices[action] for action in transitions_filtered['NextAction']]
    values = transitions_filtered['count'].tolist()

    # Create Sankey diagram
    fig = go.Figure(go.Sankey(
        node=dict(
            pad=15,
            thickness=30,
            line=dict(color="black", width=0.5),
            label=all_actions,
            hovertemplate='Node: %{label}<extra></extra>'
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            hovertemplate='Source: %{source.label}<br>Target: %{target.label}<br>Value: %{value}<extra></extra>'
        )
    ))

    fig.update_layout(title_text="Flow of User Activities", font_size=10)

    return fig_spikes, individual_sequence_fig, group_sequence_fig, spikes_fig, timeline_fig, most_edited_nodes_fig, most_active_user_fig, activity_fig, active_users_fig, heatmap_fig, pie_chart_fig, line_chart_fig, stacked_bar_fig, active_commenters_fig, comment_trends_fig, fig_user_contribution, fig

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True, port=8059)
