import boto3
import pandas as pd
import os
import shutil
from datetime import datetime, timedelta
import plotly.graph_objs as go
from plotly.offline import plot
from jinja2 import Template

# AWS Resources
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

# Constants
TABLE_NAME = 'ProgressTracker'
BUCKET_NAME = 's33ding-progress'
ITEM_TEMPLATE = '''
<html>
<head><title>Progress Report</title>
<style>
    body {
        background-color: #1b1b1b;
        font-family: 'Arial', sans-serif;
        color: #f0f0f0;
        margin: 0;
        padding: 0;
    }
    h1 {
        text-align: center;
        color: #00b7ff;
        font-size: 2.5em;
        padding-top: 50px;
    }
    table {
        width: 80%;
        margin: 20px auto;
        border-collapse: collapse;
    }
    table, th, td {
        border: 2px solid #00b7ff;
        color: #f0f0f0;
    }
    th, td {
        padding: 10px;
        text-align: center;
    }
    th {
        background-color: #333;
    }
    td {
        background-color: #444;
    }
    .graph-container {
        margin: 50px auto;
        width: 90%;
        max-width: 800px;
        border: 2px solid #00b7ff;
        padding: 20px;
        background-color: #333;
    }
</style>
</head>
<body>
<h1>Progress for {{ item_id }}</h1>
<table>
<tr><th>Timestamp</th><th>Progress (%)</th></tr>
{% for row in data %}
<tr><td>{{ row['Timestamp'] }}</td><td>{{ row['ProgressPercentage'] }}</td></tr>
{% endfor %}
</table>
<div class="graph-container">{{ graph_div | safe }}</div>
</body>
</html>
'''

HOMEPAGE_TEMPLATE = '''
<html>
<head><title>All Progress Items</title>
<style>
    body {
        background-color: #1b1b1b;
        font-family: 'Arial', sans-serif;
        color: #f0f0f0;
        margin: 0;
        padding: 0;
    }
    h1 {
        text-align: center;
        color: #00b7ff;
        font-size: 3em;
        margin-top: 50px;
    }
    ul {
        list-style-type: none;
        padding: 0;
        text-align: center;
    }
    li {
        margin: 20px 0;
    }
    a {
        color: #00b7ff;
        font-size: 1.5em;
        text-decoration: none;
        transition: color 0.3s;
    }
    a:hover {
        color: #ff4081;
    }
</style>
</head>
<body>
<h1>Tracked Items</h1>
<ul>
{% for item_id in item_ids %}
<li><a href="{{ item_id }}/index.html">{{ item_id }}</a></li>
{% endfor %}
</ul>
</body>
</html>
'''

def create_progress_graph(df, item_id):
    # Create a trace for the plot with line and markers
    trace = go.Scatter(
        x=df['Timestamp'], 
        y=df['ProgressPercentage'], 
        mode='lines+markers', 
        name='Progress'
    )

    # Define layout with y-axis range from 0 to 100 for progress percentage
    layout = go.Layout(
        title=f'Progress Over Time - {item_id}',
        xaxis=dict(title='Time'),
        yaxis=dict(title='Progress %', range=[0, 100]),  # Fixed y-axis range 0 to 100
    )

    # Create figure with the data and layout
    fig = go.Figure(data=[trace], layout=layout)

    # Generate and return the HTML div for embedding the plot
    graph_div = plot(fig, output_type='div', include_plotlyjs='cdn')
    return graph_div

def write_progress():
    table = dynamodb.Table(TABLE_NAME)
    response = table.scan(ProjectionExpression='ItemID')
    item_ids = sorted(set(item['ItemID'] for item in response['Items']))
    if not item_ids:
        print("No items found. Please create one first.")
        return

    print("Select an existing item:")
    for idx, item_id in enumerate(item_ids):
        print(f"{idx + 1}. {item_id}")
    selected = int(input("Enter the number: ")) - 1
    item_id = item_ids[selected]

    progress = int(input("Enter current progress % (e.g., 72): "))
    timestamp = (datetime.utcnow() - timedelta(hours=3)).isoformat()

    table.put_item(Item={
        'ItemID': item_id,
        'Timestamp': timestamp,
        'ProgressPercentage': progress
    })

    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('ItemID').eq(item_id)
    )
    items = sorted(response['Items'], key=lambda x: x['Timestamp'])

    df = pd.DataFrame(items)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df['ProgressPercentage'] = df['ProgressPercentage'].astype(int)

    os.makedirs(f'temp/{item_id}', exist_ok=True)

    # Create the progress graph
    graph_div = create_progress_graph(df, item_id)

    # Generate HTML content for the progress report
    html = Template(ITEM_TEMPLATE).render(item_id=item_id, data=items, graph_div=graph_div)
    with open(f'temp/{item_id}/index.html', 'w') as f:
        f.write(html)

    # Upload to S3
    s3.upload_file(f'temp/{item_id}/index.html', BUCKET_NAME, f'{item_id}/index.html', ExtraArgs={'ContentType': 'text/html'})

    shutil.rmtree(f'temp/{item_id}')
    generate_homepage()

    print(f"Progress uploaded to: https://{BUCKET_NAME}.s3.amazonaws.com/{item_id}/index.html")


def create_item():
    item_id = input("Enter new ItemID: ")
    table = dynamodb.Table(TABLE_NAME)
    timestamp = (datetime.utcnow() - timedelta(hours=3)).isoformat()
    table.put_item(Item={
        'ItemID': item_id,
        'Timestamp': timestamp,
        'ProgressPercentage': 0
    })
    print(f"Item {item_id} created.")
    generate_homepage()


def delete_item():
    table = dynamodb.Table(TABLE_NAME)
    items = table.scan()['Items']
    unique_ids = sorted(set(item['ItemID'] for item in items))

    if not unique_ids:
        print("No items to delete.")
        return

    print("Existing Items:")
    for i, item_id in enumerate(unique_ids):
        print(f"{i + 1}. {item_id}")

    index = int(input("Select item to delete: ")) - 1
    confirm = input(f"Type DELETE to confirm deletion of '{unique_ids[index]}': ")
    if confirm != 'DELETE':
        print("Cancelled.")
        return

    item_id = unique_ids[index]
    to_delete = [i for i in items if i['ItemID'] == item_id]
    for entry in to_delete:
        table.delete_item(Key={'ItemID': entry['ItemID'], 'Timestamp': entry['Timestamp']})

    s3_objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=f"{item_id}/")
    if 'Contents' in s3_objects:
        for obj in s3_objects['Contents']:
            s3.delete_object(Bucket=BUCKET_NAME, Key=obj['Key'])

    print(f"Item '{item_id}' deleted from DynamoDB and S3.")
    generate_homepage()


def print_urls():
    table = dynamodb.Table(TABLE_NAME)
    items = table.scan(ProjectionExpression='ItemID')['Items']
    unique_ids = sorted(set(item['ItemID'] for item in items))
    if not unique_ids:
        print("No items found.")
        return

    print("\nPublished URLs:")
    for item_id in unique_ids:
        print(f"- https://{BUCKET_NAME}.s3.amazonaws.com/{item_id}/index.html")
    print(f"\nHomepage: https://{BUCKET_NAME}.s3.amazonaws.com/index.html")


def generate_homepage():
    table = dynamodb.Table(TABLE_NAME)
    items = table.scan(ProjectionExpression='ItemID')['Items']
    item_ids = sorted(set(item['ItemID'] for item in items))
    html = Template(HOMEPAGE_TEMPLATE).render(item_ids=item_ids)
    with open('temp/index.html', 'w') as f:
        f.write(html)
    s3.upload_file('temp/index.html', BUCKET_NAME, 'index.html', ExtraArgs={'ContentType': 'text/html'})
    os.remove('temp/index.html')


def update_all_pages():
    print("Updating all pages without inserting new data...")

    # Regenerate all progress pages
    table = dynamodb.Table(TABLE_NAME)
    response = table.scan(ProjectionExpression='ItemID')
    item_ids = sorted(set(item['ItemID'] for item in response['Items']))

    for item_id in item_ids:
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('ItemID').eq(item_id)
        )
        items = sorted(response['Items'], key=lambda x: x['Timestamp'])

        df = pd.DataFrame(items)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        df['ProgressPercentage'] = df['ProgressPercentage'].astype(int)

        os.makedirs(f'temp/{item_id}', exist_ok=True)

        # Create the progress graph
        graph_div = create_progress_graph(df, item_id)

        # Generate HTML content for the progress report
        html = Template(ITEM_TEMPLATE).render(item_id=item_id, data=items, graph_div=graph_div)
        with open(f'temp/{item_id}/index.html', 'w') as f:
            f.write(html)

        # Upload to S3
        s3.upload_file(f'temp/{item_id}/index.html', BUCKET_NAME, f'{item_id}/index.html', ExtraArgs={'ContentType': 'text/html'})
        shutil.rmtree(f'temp/{item_id}')

    # Regenerate the homepage
    generate_homepage()


def main():
    while True:
        print("""
Choose an action:
1. Write Progress
2. Create Item
3. Delete Item
4. Show Published URLs
5. Update All Pages (without inserting data)
6. Exit
        """)
        choice = input("Enter choice [1-6]: ").strip()
        if choice == '1':
            write_progress()
        elif choice == '2':
            create_item()
        elif choice == '3':
            delete_item()
        elif choice == '4':
            print_urls()
        elif choice == '5':
            update_all_pages()
        elif choice == '6':
            print("Goodbye!")
            break
        else:
            print("Invalid option. Please try again.")


if __name__ == '__main__':
    main()

