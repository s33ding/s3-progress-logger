import boto3
import pandas as pd
import os
import shutil
from datetime import datetime, timedelta
from plotly.graph_objs import Scatter, Layout, Figure
from plotly.offline import plot
from jinja2 import Template
import subprocess
import webbrowser

# AWS Resources
session = boto3.Session(profile_name='s33ding')
dynamodb = session.resource('dynamodb')
s3 = session.client('s3')

# Constants
TABLE_NAME = 'ProgressTracker'
BUCKET_NAME = 's33ding-progress'
BASE_URL = f'https://{BUCKET_NAME}.s3.amazonaws.com'

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
    /* Home button */
    .home-nav {
        width: 90%;
        max-width: 800px;
        margin: 24px auto 60px;
        display: flex;
        justify-content: center;
    }
    .home-btn {
        display: inline-block;
        padding: 12px 18px;
        border: 2px solid #00b7ff;
        border-radius: 10px;
        text-decoration: none;
        color: #00b7ff;
        font-weight: 600;
        background: transparent;
        transition: transform .05s ease, background-color .2s ease, color .2s ease;
    }
    .home-btn:hover,
    .home-btn:focus {
        background-color: #00b7ff;
        color: #1b1b1b;
        outline: none;
    }
    .home-btn:active {
        transform: translateY(1px);
    }
</style>
</head>
<body>
<h1>Progress for {{ item_id }}</h1>

<table>
<tr><th>Timestamp</th><th>Progress (%)</th></tr>
{% for row in data %}
<tr>
    <td>{{ row['Timestamp'] }}</td>
    <td>{{ row['ProgressPercentage'] }}</td>
</tr>
{% endfor %}
</table>

<div class="graph-container">
    {{ graph_div | safe }}
</div>

<div class="home-nav">
    <a class="home-btn" href="https://s33ding-progress.s3.amazonaws.com/index.html" aria-label="Go to homepage">← Home</a>
</div>

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
    .links-container {
        display: block;
        margin-top: 40px;
        text-align: center;
        font-size: 1.2em;
    }
    .subtle-links a {
        color: #9e9e9e;
        font-size: 1em;
        opacity: 0.8;
        transition: color 0.3s, opacity 0.3s;
    }
    .subtle-links a:hover {
        color: #ff4081;
        opacity: 1;
    }
    table {
        width: 90%;
        margin: 40px auto;
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
</style>
</head>
<body>
<h1>Tracked Items</h1>
<ul>
{% for item_id in item_ids %}
<li><a href="{{ base_url }}/{{ item_id }}/index.html">{{ item_id }}</a></li>
{% endfor %}
</ul>



<div class="graph-container">
    <h2 style="text-align:center;">Latest Progress Overview</h2>
    <table>
        <tr><th>Item ID</th><th>Latest Timestamp</th><th>Progress (%)</th></tr>
        {% for row in latest_progress %}
        <tr>
            <td><a href="{{ base_url }}/{{ row['ItemID'] }}/index.html">{{ row['ItemID'] }}</a></td>
            <td>{{ row['Timestamp'] }}</td>
            <td>{{ row['ProgressPercentage'] }}</td>
        </tr>
        {% endfor %}
    </table>
</div>

<div class="links-container subtle-links">
    <a href="https://github.com/s33ding?tab=projects" target="_blank">View my GitHub Projects</a><br><br>
    <a href="https://robertomdiniz.s3.amazonaws.com/accomplishments.html" target="_blank">View my Accomplishments</a><br><br>
    <a href="https://robertomdiniz.s3.amazonaws.com/roberto-resume.pdf" target="_blank">View my Resume</a>
</div>

</body>
</html>
'''

def create_progress_graph(df, item_id):
    trace = Scatter(x=df['Timestamp'], y=df['ProgressPercentage'], mode='lines+markers', name='Progress')
    layout = Layout(title=f'Progress Over Time - {item_id}', xaxis=dict(title='Time'), yaxis=dict(title='Progress %', range=[0, 100]))
    fig = Figure(data=[trace], layout=layout)
    return plot(fig, output_type='div', include_plotlyjs='cdn')

def write_progress():
    table = dynamodb.Table(TABLE_NAME)
    response = table.scan(ProjectionExpression='ItemID')
    item_ids = sorted(set(item['ItemID'] for item in response['Items']))
    if not item_ids:
        print("No items found.")
        return

    print("Select an existing item:")
    for idx, item_id in enumerate(item_ids):
        print(f"{idx + 1}. {item_id}")
    selected = int(input("Enter the number: ")) - 1
    item_id = item_ids[selected]

    progress = int(input("Enter current progress %: "))
    timestamp = (datetime.utcnow() - timedelta(hours=3)).isoformat()

    table.put_item(Item={'ItemID': item_id, 'Timestamp': timestamp, 'ProgressPercentage': progress})
    response = table.query(KeyConditionExpression=boto3.dynamodb.conditions.Key('ItemID').eq(item_id))
    items = sorted(response['Items'], key=lambda x: x['Timestamp'])

    df = pd.DataFrame(items)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df['ProgressPercentage'] = df['ProgressPercentage'].astype(int)

    os.makedirs(f'temp/{item_id}', exist_ok=True)
    graph_div = create_progress_graph(df, item_id)
    html = Template(ITEM_TEMPLATE).render(item_id=item_id, data=items, graph_div=graph_div)
    with open(f'temp/{item_id}/index.html', 'w') as f:
        f.write(html)

    s3.upload_file(f'temp/{item_id}/index.html', BUCKET_NAME, f'{item_id}/index.html', ExtraArgs={'ContentType': 'text/html'})
    shutil.rmtree(f'temp/{item_id}')
    generate_homepage()
    print(f"Uploaded: {BASE_URL}/{item_id}/index.html")

    # NEW: open the freshly published page in Firefox
    url = f"{BASE_URL}/{item_id}/index.html"
    if _open_in_firefox_new_window(url):
        print(f"Opening in Firefox: {url}")
    else:
        print(f"Couldn't open in Firefox automatically. Please open manually: {url}")

    print(f"Uploaded: {url}")


def create_item():
    item_id = input("Enter new ItemID: ")
    table = dynamodb.Table(TABLE_NAME)
    timestamp = (datetime.utcnow() - timedelta(hours=3)).isoformat()
    table.put_item(Item={'ItemID': item_id, 'Timestamp': timestamp, 'ProgressPercentage': 0})
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

    print(f"Deleted '{item_id}' from DynamoDB and S3.")
    generate_homepage()


def _open_in_firefox_new_window(url: str) -> bool:
    """Linux-only: open URL in Firefox as a new window; return True on success."""
    # 1) Native Firefox on PATH
    exe = shutil.which("firefox")
    if exe:
        try:
            subprocess.Popen([exe, "--new-window", url])
            return True
        except Exception:
            pass

    # 2) Flatpak Firefox
    if shutil.which("flatpak"):
        try:
            subprocess.Popen(["flatpak", "run", "org.mozilla.firefox", "--new-window", url])
            return True
        except Exception:
            pass

    # 3) Snap Firefox
    if shutil.which("snap"):
        try:
            subprocess.Popen(["snap", "run", "firefox", "--new-window", url])
            return True
        except Exception:
            pass

    # 4) Last resort: whatever the system default is
    try:
        webbrowser.open(url, new=1)
        return True
    except Exception:
        return False


def print_urls():
    table = dynamodb.Table(TABLE_NAME)
    items = table.scan(ProjectionExpression='ItemID').get('Items', [])
    unique_ids = sorted({item.get('ItemID') for item in items if 'ItemID' in item})

    if not unique_ids:
        print("No items found.")
        return

    urls = [f"{BASE_URL}/{item_id}/index.html" for item_id in unique_ids]
    homepage = f"{BASE_URL}/index.html"

    print("\nPublished URLs:")
    for i, url in enumerate(urls, start=1):
        print(f"{i}. {url}")
    print(f"h. Homepage: {homepage}")

    choice = input("\nChoose one to open in Firefox (number, 'h' for homepage, or Enter to skip): ").strip().lower()
    if not choice:
        print("Skipping open.")
        return

    target = None
    if choice == 'h':
        target = homepage
    else:
        try:
            idx = int(choice)
            if 1 <= idx <= len(urls):
                target = urls[idx - 1]
        except ValueError:
            pass

    if not target:
        print("Invalid selection.")
        return

    if _open_in_firefox_new_window(target):
        print(f"Opening in Firefox: {target}")
    else:
        print(f"Couldn't open in Firefox automatically. Please open manually: {target}")


def generate_homepage():
    table = dynamodb.Table(TABLE_NAME)
    response = table.scan()
    items = response['Items']
    item_ids = sorted(set(item["ItemID"] for item in items))

    latest_entries = {}
    for item in items:
        item_id = item['ItemID']
        ts = item['Timestamp']
        if (item_id not in latest_entries) or (ts > latest_entries[item_id]['Timestamp']):
            latest_entries[item_id] = item

    latest_progress = sorted(latest_entries.values(), key=lambda x: x['ProgressPercentage'], reverse=True)


    html = Template(HOMEPAGE_TEMPLATE).render(
        item_ids=item_ids,
        latest_progress=latest_progress,
        base_url=BASE_URL
    )

    os.makedirs("temp", exist_ok=True)
    with open('temp/index.html', 'w') as f:
        f.write(html)
    s3.upload_file('temp/index.html', BUCKET_NAME, 'index.html', ExtraArgs={'ContentType': 'text/html'})
    os.remove('temp/index.html')

def update_all_pages():
    print("Updating all pages...")
    table = dynamodb.Table(TABLE_NAME)
    response = table.scan(ProjectionExpression='ItemID')
    item_ids = sorted(set(item['ItemID'] for item in response['Items']))

    for item_id in item_ids:
        response = table.query(KeyConditionExpression=boto3.dynamodb.conditions.Key('ItemID').eq(item_id))
        items = sorted(response['Items'], key=lambda x: x['Timestamp'])

        df = pd.DataFrame(items)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        df['ProgressPercentage'] = df['ProgressPercentage'].astype(int)

        os.makedirs(f'temp/{item_id}', exist_ok=True)
        graph_div = create_progress_graph(df, item_id)
        html = Template(ITEM_TEMPLATE).render(item_id=item_id, data=items, graph_div=graph_div)
        with open(f'temp/{item_id}/index.html', 'w') as f:
            f.write(html)

        s3.upload_file(f'temp/{item_id}/index.html', BUCKET_NAME, f'{item_id}/index.html', ExtraArgs={'ContentType': 'text/html'})
        shutil.rmtree(f'temp/{item_id}')

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
            print("Invalid option. Try again.")

if __name__ == '__main__':
    main()

