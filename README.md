# 🚀 Nexus Core

**Nexus Core** is a web-based **PC Digital Twin and Predictive Maintenance Platform** designed to monitor computer systems in real time, track system health, detect potential issues, and manage maintenance activities from a centralized dashboard.

The platform combines a **Flask web application, MySQL database, Python monitoring agent, predictive maintenance logic, system history, ticket management, inventory management, and a modern monitoring dashboard**.

---

## 📌 Overview

Nexus Core continuously collects system information from connected computers through the Nexus Core Agent and displays the information through a centralized web dashboard.

The system is designed to help monitor:

* CPU usage
* RAM usage
* Disk usage
* GPU information
* VRAM
* Battery status
* System uptime
* Operating system
* IP address
* Storage information
* System hardware information
* System health
* Heartbeat / connectivity status

The collected information can then be used for system monitoring and predictive maintenance.

---

# ✨ Features

## 🖥️ PC Monitoring

Nexus Core provides real-time monitoring of connected systems.

### System Metrics

* CPU utilization
* RAM utilization
* Disk utilization
* GPU information
* GPU VRAM
* Battery status
* System uptime
* Operating system
* IP address
* CPU model
* RAM capacity
* Storage information
* Motherboard/system information
* BIOS information
* System architecture

---

## 💓 System Health Monitoring

Each connected system can be monitored based on its current health and connectivity.

Supported system states include:

```text
ONLINE
HEALTHY
WARNING
CRITICAL
OFFLINE
```

The dashboard provides health indicators to quickly identify systems that may require attention.

---

## 🔮 Predictive Maintenance

Nexus Core includes predictive maintenance functionality that analyzes system conditions and identifies potential maintenance requirements.

Examples include:

* High CPU utilization
* High RAM utilization
* Low available disk space
* Critical battery level
* Low battery while not charging
* Extended system uptime
* Connectivity / heartbeat problems
* Critical system health conditions

The system can generate maintenance recommendations based on detected conditions.

---

## 🔧 Maintenance Management

The Maintenance module allows users to manage planned maintenance activities.

Features include:

* Maintenance recommendations
* Maintenance planning
* Scheduled maintenance
* Maintenance status
* Priority management
* Estimated maintenance cost
* Replacement dates
* Maintenance tracking
* System-focused maintenance information

---

## 🎫 Ticket Management

Nexus Core includes a support ticket system for managing system-related issues.

Tickets can contain:

* Title
* Description
* Priority
* Category
* Status
* Due date
* Comments
* Activity history

This allows system issues to be tracked from creation through resolution.

---

## 📦 Inventory Management

The Inventory module can be used to track hardware and other system-related inventory information.

This can help maintain a centralized record of hardware resources associated with monitored systems.

---

## 📊 System History

Nexus Core stores monitoring information so system performance and health can be reviewed over time.

Historical information can be used to understand:

* CPU usage trends
* RAM usage trends
* Disk usage
* System health
* System activity
* Connectivity
* Previous monitoring conditions

---

## 👤 Authentication & User Management

Nexus Core includes authentication and account management functionality.

Supported functionality includes:

* User registration
* User login
* User logout
* User profiles
* Password management
* Password recovery
* Role-based access
* Administrator controls

---

## 📱 QR System Identification

Nexus Core also provides QR-based system identification functionality.

QR codes can be used to identify monitored systems and quickly access system-related information.

---

## 🌙 Modern Dashboard

The Nexus Core interface is designed as a modern monitoring dashboard with:

* Dark mode
* Light mode
* Responsive layout
* System health cards
* KPI cards
* Status filters
* Monitoring tables
* Maintenance panels
* Alert sections
* Quick actions
* Interactive dashboard components

---

# 🏗️ System Architecture

The basic Nexus Core architecture is:

```text
                    ┌──────────────────────┐
                    │    Monitored PC      │
                    │                      │
                    │  Nexus Core Agent    │
                    │      (Python)        │
                    └──────────┬───────────┘
                               │
                               │ System Metrics
                               │
                               ▼
                    ┌──────────────────────┐
                    │    Flask Backend     │
                    │                      │
                    │    Nexus Core API    │
                    └──────────┬───────────┘
                               │
                               │ SQLAlchemy
                               │
                               ▼
                    ┌──────────────────────┐
                    │     MySQL Database   │
                    │                      │
                    │ predictive_maintenance
                    └──────────┬───────────┘
                               │
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Nexus Core Web     │
                    │      Dashboard       │
                    │                      │
                    │ Monitoring / Alerts  │
                    │ Maintenance / Tickets│
                    └──────────────────────┘
```

---

# 🛠️ Technology Stack

## Backend

* Python
* Flask
* Flask-SQLAlchemy
* SQLAlchemy
* Gunicorn
* Requests

## Database

* MySQL
* PyMySQL

## System Monitoring

* psutil

## Frontend

* HTML5
* CSS3
* JavaScript
* Bootstrap
* Font Awesome

## Deployment

* Docker
* Gunicorn
* Render

---

# 📂 Project Structure

```text
nexus-core/
│
├── app.py
├── agent.py
├── config.py
├── database.py
├── models.py
├── requirements.txt
├── Dockerfile
│
├── data/
│
├── static/
│   ├── css/
│   ├── js/
│   ├── images/
│   └── downloads/
│
├── templates/
│   ├── dashboard.html
│   ├── login.html
│   ├── register.html
│   ├── profile.html
│   ├── settings.html
│   ├── systems.html
│   ├── predictions.html
│   ├── maintenance.html
│   ├── inventory.html
│   ├── tickets.html
│   ├── alerts.html
│   ├── qr.html
│   └── about.html
│
└── README.md
```

---

# ⚙️ Installation

## 1. Clone the Repository

```bash
git clone https://github.com/gggtg314-gif/nexus-core.git
```

Enter the project directory:

```bash
cd nexus-core
```

---

## 2. Create a Virtual Environment

### Windows

```bash
python -m venv venv
```

Activate the virtual environment:

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv venv
```

Activate it:

```bash
source venv/bin/activate
```

---

# 📦 3. Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

---

# 🗄️ 4. Configure MySQL

Create the database:

```sql
CREATE DATABASE predictive_maintenance;
```

Configure the application with your MySQL credentials.

Example configuration:

```text
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=predictive_maintenance
```

> Do not commit real database passwords or secrets to GitHub.

---

# ▶️ Running the Application

Start the Flask application:

```bash
python app.py
```

After starting the server, open:

```text
http://localhost:5000
```

---

# 🤖 Nexus Core Agent

The **Nexus Core Agent** is a Python-based monitoring agent that runs on monitored computers.

The agent collects system information and sends the information to the Nexus Core backend.

## Agent Data

The agent can collect:

```text
CPU
RAM
Disk
GPU
VRAM
Battery
Operating System
IP Address
System Uptime
CPU Model
RAM Capacity
Storage
Motherboard
BIOS
Architecture
```

The collected data is sent to the Nexus Core server for monitoring and storage.

---

# 📡 Monitoring Flow

The basic monitoring flow is:

```text
Nexus Core Agent
       │
       ▼
Collect System Metrics
       │
       ▼
Send Data to Flask API
       │
       ▼
Store Data in MySQL
       │
       ▼
Process System Health
       │
       ▼
Display on Dashboard
       │
       ▼
Generate Maintenance Insights
```

---

# 🚦 System Status

Nexus Core uses system conditions and heartbeat information to determine the current system state.

Possible states:

### 🟢 Online

The monitored system is communicating with the Nexus Core server.

### 🔵 Healthy

The system is operating within configured healthy thresholds.

### 🟡 Warning

One or more monitored metrics have reached a warning condition.

### 🔴 Critical

One or more monitored metrics have reached a critical condition.

### ⚫ Offline

The system has not provided a recent heartbeat or is otherwise considered unavailable.

---

# 📈 Dashboard

The main dashboard provides an overview of connected systems.

Dashboard information can include:

```text
Total Systems
Online Systems
Healthy Systems
Warning Systems
Critical Systems
Offline Systems
CPU Usage
RAM Usage
Disk Usage
Recent Alerts
Maintenance Recommendations
System History
```

---

# 🔍 System Filtering

The Systems page provides status filtering.

Available filters include:

```text
All Status
Online
Healthy
Warning
Critical
Offline
```

This makes it easier to locate systems that require attention.

---

# 🔮 Predictive Maintenance Logic

Nexus Core can identify potentially problematic conditions using configured monitoring thresholds.

Examples:

```text
CPU Usage
      ↓
Warning / Critical

RAM Usage
      ↓
Warning / Critical

Disk Usage
      ↓
Warning / Critical

Battery Level
      ↓
Warning / Critical

System Uptime
      ↓
Maintenance Information

Heartbeat
      ↓
Online / Offline
```

The exact thresholds can be configured according to deployment requirements.

---

# 🔧 Maintenance Planner

The Maintenance Planner allows users to create and manage planned maintenance activities.

Maintenance records can include:

```text
System
Priority
Estimated Cost
Replacement Date
Status
Description
```

This helps organize future maintenance activities.

---

# 🎫 Ticket Workflow

A typical ticket workflow can be:

```text
Create Ticket
     │
     ▼
Open
     │
     ▼
In Progress
     │
     ▼
Resolved
     │
     ▼
Closed
```

Tickets can also include comments and activity information.

---

# 🐳 Docker

Nexus Core supports containerized deployment.

## Build Docker Image

```bash
docker build -t nexus-core .
```

## Run Container

```bash
docker run -p 5000:5000 nexus-core
```

Then open:

```text
http://localhost:5000
```

---

# 🌐 Production Deployment

Nexus Core can be deployed using container-based hosting platforms such as **Render**.

A production deployment can use:

```text
                    Internet
                       │
                       ▼
                ┌─────────────┐
                │   Render    │
                │ Web Service │
                └──────┬──────┘
                       │
                       ▼
                ┌─────────────┐
                │   Gunicorn  │
                │    Flask    │
                └──────┬──────┘
                       │
                       ▼
                ┌─────────────┐
                │    MySQL    │
                │   Database  │
                └─────────────┘
```

For production deployments, database credentials and other secrets should be configured using environment variables.

---

# 🔐 Security

Before deploying Nexus Core publicly:

* Use strong database credentials
* Use environment variables for secrets
* Never commit passwords to GitHub
* Never commit API keys
* Disable Flask debug mode in production
* Use HTTPS
* Use secure session configuration
* Restrict database permissions
* Keep dependencies updated

Example:

```text
.env
```

should not be committed if it contains secrets.

Add sensitive files to `.gitignore`:

```text
.env
venv/
__pycache__/
*.pyc
```

---

# 📋 Configuration

Important application configuration can include:

```text
Database Host
Database Port
Database Name
Database Username
Database Password
Server Host
Server Port
Agent Interval
Offline Threshold
CPU Warning Threshold
CPU Critical Threshold
RAM Warning Threshold
RAM Critical Threshold
Disk Warning Threshold
Disk Critical Threshold
Dashboard Refresh Interval
```

These values can be adjusted according to the deployment environment.

---

# 🔮 Future Development

Potential future improvements include:

* 🌡️ IoT temperature monitoring
* 💧 Humidity monitoring
* 📳 Vibration monitoring
* 🌐 IoT device management
* 📊 Advanced analytics
* 🤖 Improved predictive models
* 📧 Maintenance notifications
* 🔔 Automated alerts
* 📱 Mobile dashboard
* 📈 Advanced historical charts
* 🔄 Automated agent updates
* 🧠 Machine-learning-based failure prediction
* ☁️ Improved cloud deployment
* 🔐 Advanced security controls

---

# 📸 Project Screens

The Nexus Core dashboard includes interfaces for:

```text
Dashboard
Systems
Predictions
Maintenance
Inventory
Tickets
Alerts
QR
Profile
Settings
```

Screenshots can be added here as the project develops.

Example:

```markdown
![Nexus Core Dashboard](screenshots/dashboard.png)
```

---

# 📌 Project Status

**Nexus Core is an actively developed project.**

The current platform focuses on:

```text
PC Monitoring
       +
System Health
       +
Predictive Maintenance
       +
Maintenance Management
       +
Ticket Management
       +
Inventory Management
```

---

# 🎯 Project Goal

The primary goal of Nexus Core is to provide a centralized platform for monitoring computer systems and identifying potential maintenance requirements before they become major issues.

The project combines system monitoring, data collection, health analysis, and maintenance management into a single web-based platform.

---

# 👨‍💻 Author

## Nexus Core

GitHub Repository:

https://github.com/gggtg314-gif/nexus-core

---

# 📄 License

This project is currently intended for educational, research, and development purposes.

A formal open-source license can be added to the repository if the project is released under a specific license.

---

# ⭐ Support

If you find the project useful, consider giving the repository a ⭐ on GitHub.

---

## 🚀 Nexus Core

**Monitor. Analyze. Predict. Maintain.**
