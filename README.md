# Predict-Aerosols

## Description

An AI based cloud platform to predict the real time concentration of Aerosols over a region using Google Earth Engine.

## Acknowledgement

> Project proposed for Department of Space Applicationns, Space Studies Program 2024 organised by International Space University in collaboration with NASA Johnson Space Center at Rice University Houston, Texas, USA.

## Authors

> **_Ashutosh Mishra_**, Doctoral Researcher (MEXT Scholar) at Space Robotics Laboratory, Tohoku University, Japan

> ***Mahesh Pathakoti***, Scientist/Engineer-SF, National Remote Sensing Centre, Indian Space Reserach Organisation (ISRO), India

---

---

## Installation on AWS Server

### Prerequisites

1. **AWS Account**: Ensure you have access to an AWS EC2 instance.
2. **Instance Setup**:
   - Launch an EC2 instance with a suitable configuration (e.g., t2.micro for testing).
   - Use an Amazon Machine Image (AMI) with Ubuntu or Amazon Linux.
   - Open ports in the security group:
     - **22**: SSH access
     - **80**: HTTP (if deploying a web app)
     - **443**: HTTPS (optional, for SSL)
3. **Domain Name** (Optional): Ensure your domain points to your AWS server.

### Step 1: SSH into AWS Instance

    ssh -i your-key.pem ubuntu@your-ec2-public-ip

### Step 2: Update Packages

    sudo apt update && sudo apt upgrade -y

### Step 3: Install Dependencies

    sudo apt install -y python3 python3-pip git unzip python3-venv apache2 libapache2-mod-wsgi-py3

### Step 4: Clone the Repository

    git clone "https://github.com/https://github.com/drashutoshspace/SSTA-Smart-System-for-Tracking-Airpollution"
    mv SSTA-Smart-System-for-Tracking-Airpollution ssta
    cd ssta

### Step 5: Set Up Virtual Environment

    python3 -m venv .venv
    source venv/bin/activate

### Step 6: Install Python Dependencies

    pip install -r requirements.txt

### Step 7: Test Flask App Locally (Optional)

    python flaskapp/app.py

### Step 8: Configure Apache for Your Flask App

#### Create a new Apache configuration file

Change Domain name and server name accordingly
    sudo bash -c 'cat > /etc/apache2/sites-available/ssta.conf << EOF
    <VirtualHost *:80>

        ServerName your-domain-or-ip
        ServerAdmin webmaster@localhost

        #WSGIDaemonProcess myflaskapp python-path=/home/ubuntu/ssta python-home=/home/ubuntu/ssta/.venv
        #WSGIProcessGroup myflaskapp
        #WSGIScriptAlias / /home/ubuntu/ssta/wsgi.py

        <Directory /home/ubuntu/ssta>
            Require all granted
        </Directory>

        Alias /static /home/ubuntu/ssta/flaskapp/static
        <Directory /home/ubuntu/ssta/flaskapp/static>
            Require all granted
        </Directory>

        ErrorLog ${APACHE_LOG_DIR}/ssta_error.log
        CustomLog ${APACHE_LOG_DIR}/ssta_access.log combined

    </VirtualHost>
    EOF'

### Step 9: Enable the Apache Configuration

    sudo a2ensite ssta.conf
    sudo a2enmod wsgi
    sudo systemctl restart apache2

### Step 10: Verify the Setup

### Check if Apache is running and no errors exist

    sudo systemctl status apache2
    sudo tail -f /var/log/apache2/ssta_error.log

### Access the Application

Visit http://your-domain-or-ip in your browser

# Google Earth API Setup with Service Account

## Overview
This guide helps you create and configure a Google Cloud Service Account to access Google Earth APIs. A service account allows server-to-server communication, enabling your application to use Google Earth Engine resources securely.

---

## Prerequisites
1. A **Google Cloud Platform (GCP)** account.
2. Basic knowledge of Python (if using Python for implementation).
3. `gcloud` CLI installed (optional, for advanced users).

---

## Setup Instructions

### Step 1: Create a Google Cloud Project
1. Log in to the [Google Cloud Console](https://console.cloud.google.com/).
2. Select **New Project** and provide a project name (e.g., `GoogleEarthAPIProject`).
3. Once the project is created, select it from the dropdown at the top.

### Step 2: Enable Required APIs
1. Navigate to **APIs & Services > Library**.
2. Enable the following APIs:
   - **Google Earth Engine API**
   - **Maps JavaScript API** (if applicable for your project).

### Step 3: Create a Service Account
1. Go to **IAM & Admin > Service Accounts**.
2. Click **Create Service Account**.
3. Provide:
   - **Service Account Name**: e.g., `google-earth-api-sa`.
   - **Description** (optional): e.g., `Service account for accessing Google Earth Engine API`.
4. Click **Create and Continue**.

### Step 4: Assign Roles to the Service Account
1. Assign a role to the service account:
   - For full access, use the `Owner` role.
   - For more restrictive access, use the `Earth Engine Resource Manager` role or another relevant role.
2. Click **Continue** and then **Done**.

### Step 5: Generate a JSON Key
1. In the **Service Accounts** list, locate your newly created account.
2. Click the **Actions** menu (three vertical dots) and select **Manage Keys**.
3. Click **Add Key > Create New Key**.
4. Choose **JSON** as the key type, and download the file to your computer.
   - Save this file securely, as it contains sensitive credentials.
   - 

## Using the Service Account in Python

To authenticate with the service account and access Google Earth APIs in flaskapp, use the following setup:

- name the key file you just downloaded as creds2.json
- create a folder config in root dir of the project
- paste the creds2.json there for the application to access

## Credits & References

1. Flask: A lightweight WSGI web application framework, developed by Armin Ronacher and the Pallets Projects community. Available at: <https://flask.palletsprojects.com/>

2. Tailblocks: Ready-to-use Tailwind CSS blocks, created by Mert Cukuren. Available at: <https://mertjf.github.io/tailblocks/>

3. Google Earth Engine: A cloud-based platform for planetary-scale environmental data analysis. Available at: <https://earthengine.google.com/>

4. Updating Soon
