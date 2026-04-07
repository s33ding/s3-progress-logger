import boto3
import pandas as pd
import os
import shutil
from datetime import datetime, timedelta, timezone
from plotly.graph_objs import Scatter, Layout, Figure
from plotly.offline import plot
from jinja2 import Template, Environment
import subprocess
import webbrowser
from urllib.parse import quote

# AWS Resources
session = boto3.Session(profile_name='s33ding', region_name='us-east-1')
dynamodb = session.resource('dynamodb')
s3 = session.client('s3')

# Constants
TABLE_NAME = 'ProgressTracker'
BUCKET_NAME = 's33ding-progress'
BASE_URL = f'https://{BUCKET_NAME}.s3.amazonaws.com'

ITEM_TEMPLATE = '''
<html>
<head>
<meta charset="UTF-8">
<title>Progress Report</title>
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
        color: #66bb6a;
        font-size: 2.5em;
        padding-top: 50px;
    }
    table {
        width: 80%;
        margin: 20px auto;
        border-collapse: collapse;
    }
    table, th, td {
        border: 2px solid #66bb6a;
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
        border: 2px solid #66bb6a;
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
        border: 2px solid #66bb6a;
        border-radius: 10px;
        text-decoration: none;
        color: #66bb6a;
        font-weight: 600;
        background: transparent;
        transition: transform .05s ease, background-color .2s ease, color .2s ease;
    }
    .home-btn:hover,
    .home-btn:focus {
        background-color: #66bb6a;
        color: #1b1b1b;
        outline: none;
    }
    .home-btn:active {
        transform: translateY(1px);
    }
</style>
</head>
<body>

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
<head>
<meta charset="UTF-8">
<title>Progress Tracker</title>
<style>
    * { box-sizing: border-box; }
    body {
        background: linear-gradient(135deg, #0f0f0f 0%, #1b1b1b 100%);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #f0f0f0;
        margin: 0;
        padding: 20px;
        min-height: 100vh;
    }
    .container {
        max-width: 1200px;
        margin: 0 auto;
    }
    h1 {
        text-align: center;
        color: #66bb6a;
        font-size: 2.8em;
        margin: 30px 0 20px;
        text-shadow: 0 0 20px rgba(102, 187, 106, 0.3);
    }
    .search-box {
        max-width: 400px;
        margin: 0 auto 30px;
        position: relative;
    }
    .search-box input {
        width: 100%;
        padding: 12px 16px;
        background: rgba(30, 30, 30, 0.6);
        border: 2px solid rgba(102, 187, 106, 0.3);
        border-radius: 8px;
        color: #f0f0f0;
        font-size: 1em;
        transition: border-color 0.3s;
    }
    .search-box input:focus {
        outline: none;
        border-color: #66bb6a;
    }
    .search-box input::placeholder {
        color: #888;
    }
    .table-wrapper {
        background: rgba(30, 30, 30, 0.6);
        border-radius: 12px;
        padding: 30px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        backdrop-filter: blur(10px);
        margin-bottom: 50px;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        border-radius: 8px;
        overflow: hidden;
    }
    th {
        background: linear-gradient(135deg, #66bb6a 0%, #4a8a4e 100%);
        color: #fff;
        padding: 16px;
        text-align: left;
        font-weight: 600;
        font-size: 1.1em;
        cursor: pointer;
        user-select: none;
        position: relative;
    }
    th:hover {
        background: linear-gradient(135deg, #81c784 0%, #5a9e5e 100%);
    }
    th::after {
        content: ' ⇅';
        opacity: 0.5;
        font-size: 0.9em;
    }
    th.sort-asc::after {
        content: ' ↑';
        opacity: 1;
    }
    th.sort-desc::after {
        content: ' ↓';
        opacity: 1;
    }
    td {
        padding: 14px 16px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    tr:hover td {
        background: rgba(102, 187, 106, 0.1);
    }
    tr:last-child td {
        border-bottom: none;
    }
    td a {
        color: #66bb6a;
        text-decoration: none;
        font-weight: 500;
        transition: color 0.2s;
    }
    td a:hover {
        color: #ff4081;
    }
    .progress-bar {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        height: 24px;
        overflow: hidden;
        position: relative;
    }
    .progress-fill {
        background: linear-gradient(90deg, #66bb6a 0%, #a5d6a7 100%);
        height: 100%;
        border-radius: 10px;
        transition: width 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #fff;
        font-weight: 600;
        font-size: 0.85em;
    }
    .timestamp {
        color: #aaa;
        font-size: 0.95em;
    }
    .links-container {
        text-align: center;
        margin: 60px 0 40px;
        padding: 30px;
        background: rgba(30, 30, 30, 0.4);
        border-radius: 12px;
    }
    .links-container a {
        color: #9e9e9e;
        text-decoration: none;
        margin: 0 20px;
        font-size: 1em;
        transition: color 0.3s;
        display: inline-block;
        padding: 8px 0;
    }
    .links-container a:hover {
        color: #66bb6a;
    }
    .no-results {
        text-align: center;
        padding: 40px;
        color: #888;
        font-size: 1.1em;
    }
</style>
</head>
<body>
<div class="container">
    <h1>🌱 Progress Tracker</h1>
    
    <div class="search-box">
        <input type="text" id="searchInput" placeholder="🔍 Filter items..." onkeyup="filterTable()">
    </div>
    
    <div class="table-wrapper">
        <table id="dataTable">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Item</th>
                    <th onclick="sortTable(1)">Last Updated</th>
                    <th onclick="sortTable(2)">Progress</th>
                </tr>
            </thead>
            <tbody>
                {% for row in latest_progress %}
                <tr>
                    <td><a href="{{ base_url }}/{{ row['ItemID'] | urlencode }}/index.html">{{ row['ItemID'] }}</a></td>
                    <td class="timestamp" data-timestamp="{{ row['Timestamp'] }}">{{ row['Timestamp'][:19].replace('T', ' ') }}</td>
                    <td data-progress="{{ row['ProgressPercentage'] }}">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: {{ row['ProgressPercentage'] }}%">
                                {{ row['ProgressPercentage'] }}%
                            </div>
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        <div id="noResults" class="no-results" style="display:none;">No items found</div>
    </div>

    <div class="links-container">
        <a href="https://github.com/s33ding?tab=projects" target="_blank">GitHub Projects</a>
        <a href="https://robertomdiniz.s3.amazonaws.com/accomplishments.html" target="_blank">Accomplishments</a>
        <a href="https://robertomdiniz.s3.amazonaws.com/index.html" target="_blank">Resume</a>
    </div>
</div>

<script>
let sortDir = [1, -1, 1];

function sortTable(col) {
    const table = document.getElementById('dataTable');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const headers = table.querySelectorAll('th');
    
    headers.forEach((h, i) => {
        h.className = i === col ? (sortDir[col] === 1 ? 'sort-asc' : 'sort-desc') : '';
    });
    
    rows.sort((a, b) => {
        let aVal, bVal;
        if (col === 0) {
            aVal = a.cells[0].textContent.trim().toLowerCase();
            bVal = b.cells[0].textContent.trim().toLowerCase();
        } else if (col === 1) {
            aVal = a.cells[1].dataset.timestamp;
            bVal = b.cells[1].dataset.timestamp;
        } else {
            aVal = parseInt(a.cells[2].dataset.progress);
            bVal = parseInt(b.cells[2].dataset.progress);
        }
        return (aVal > bVal ? 1 : -1) * sortDir[col];
    });
    
    sortDir[col] *= -1;
    rows.forEach(row => tbody.appendChild(row));
}

function filterTable() {
    const input = document.getElementById('searchInput').value.toLowerCase();
    const tbody = document.querySelector('#dataTable tbody');
    const rows = tbody.querySelectorAll('tr');
    let visibleCount = 0;
    
    rows.forEach(row => {
        const text = row.cells[0].textContent.toLowerCase();
        if (text.includes(input)) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
    
    document.getElementById('noResults').style.display = visibleCount === 0 ? 'block' : 'none';
    tbody.style.display = visibleCount === 0 ? 'none' : '';
}
</script>
</body>
</html>
'''

def create_progress_graph(df, item_id):
    trace = Scatter(x=df['Timestamp'], y=df['ProgressPercentage'], mode='lines+markers', name='Progress',
                    line=dict(color='#66bb6a'), marker=dict(color='#66bb6a'))
    layout = Layout(title=dict(text=f'Progress Over Time - {item_id}', font=dict(color='#f0f0f0')),
                    xaxis=dict(title='Time', color='#aaa', gridcolor='#444'),
                    yaxis=dict(title='Progress %', range=[0, 100], color='#aaa', gridcolor='#444'),
                    paper_bgcolor='#1b1b1b', plot_bgcolor='#1b1b1b', font=dict(color='#f0f0f0'))
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
    print(f"Selected: {selected + 1}. {item_id}")

    progress = int(input("Enter current progress %: "))
    timestamp = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(microsecond=0).isoformat()

    table.put_item(Item={'ItemID': item_id, 'Timestamp': timestamp, 'ProgressPercentage': progress})
    response = table.query(KeyConditionExpression=boto3.dynamodb.conditions.Key('ItemID').eq(item_id))
    items = sorted(response['Items'], key=lambda x: x['Timestamp'])

    df = pd.DataFrame(items)
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='ISO8601')
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
    timestamp = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(microsecond=0).isoformat()
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

    latest_progress = sorted(latest_entries.values(), key=lambda x: x['Timestamp'], reverse=True)


    env = Environment()
    env.filters['urlencode'] = lambda s: quote(str(s), safe='')
    html = env.from_string(HOMEPAGE_TEMPLATE).render(
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
        df['Timestamp'] = pd.to_datetime(df['Timestamp'], format='ISO8601')
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

