# 🌱 s3-progress-logger

A cloud-native CLI tool to track and visualize daily progress using AWS services.

🚀 Live Demo: [https://s33ding-progress.s3.amazonaws.com/index.html](https://s33ding-progress.s3.amazonaws.com/index.html)

---

## 📦 Features

- ✅ Track progress on any number of user-defined items
- 📈 Generates visual progress charts with Plotly
- 🧾 Uploads full HTML reports to a public S3 static website
- 🗂️ Lists and links to all items from a central homepage
- 🛠️ Uses DynamoDB to store history with timestamps
- 🧹 CLI to create, update, delete, and browse progress logs

---

## 🔧 Tech Stack

| Component         | Tool/Service           |
|------------------|------------------------|
| CLI              | Python (no argparse)   |
| Visualization    | Plotly                 |
| Templating       | Jinja2                 |
| Data Store       | DynamoDB               |
| File Hosting     | S3 (Static Website)    |
| Infrastructure   | CloudFormation (optional) |

---

## 🚀 Getting Started

### 1. 📥 Install Dependencies

```bash
pip install boto3 plotly pandas jinja2
# s3-progress-logger
