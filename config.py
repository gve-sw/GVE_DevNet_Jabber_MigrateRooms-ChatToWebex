"""Copyright (c) 2020 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""
import os

# dCloud environment can be used for testing:
# 'Evolution of Cisco Jabber and Migration of Jabber to Webex Lab v3'

'''
DB variables to be used by SQLAlchemy to connect to DB. 
Check the DB types supported by SQLALchemy engine in its references. 
Following is a sample:
 - Postgres: postgres
 - Microsoft SQL: mssql+pymssql
 - Oracle: oracle
 - etc...
'''
# Persistent Chat DB
TC_DB_TYPE = "<db_type>"
TC_DB_HOST = "<hostname_or_ip_address_here>"
TC_DB_NAME = "tcmadb"
TC_DB_USER = "<username_here>"
TC_DB_PASSWORD = "<password_here>"

# This boolean variable is to choose to migrate the message attachments & file transfer activity (True),
# or just handle text-chat only, and display 'Your chat application does not support downloading this file'
# for messages with attachments (False)
INCLUDE_FILE_TRANSFER = False

# Managed file transfer DB
# Only if INCLUDE_FILE_TRANSFER was set to True
MFT_DB_TYPE = "<db_type>"
MFT_DB_HOST = "<hostname_or_ip_address_here>"
MFT_DB_NAME = "mftadb"
MFT_DB_USER = "<username_here>"
MFT_DB_PASSWORD = "<password_here>"

# File-transfer server details, to be able to download the files to a local folder, then forward it to Webex
# Only if INCLUDE_FILE_TRANSFER was set to True
FILE_SERVER_HOST = '<hostname_or_ip_address_here>'
FILE_SERVER_USER = '<username_here>'
FILE_SERVER_PASSWORD = '<password_here>'

# This boolean variable is to choose to migrate the detected Jabber rooms to Webex (True),
# or just use this script to read the existing Jabber rooms and their details and save them in a log (False)
CREATE_WEBEX_ROOMS = True

# This boolean variable is to choose to check for already-existing Webex rooms that have the same title as the detected Jabber room,
# then ask the user if they want to skip it (to avoid duplicates) or migrate it to new room anyway (True)
# or not checking the existing Webex rooms' titles and just create new ones anyway (False)
CHECK_WEBEX_EXISTING_ROOMS = False

# Webex Authorization
# Only if CREATE_WEBEX_ROOMS was set to True
WEBEX_AUTH = 'Bearer <webex_user_token>'

# Do you have an Excel file that maps Jabber usernames to Webex emails?
INCLUDE_JABBER_WEBEX_MAP = True


# These 2 variables are only needed if Jabber IM messaging uses a different domain than Webex domain.
# Example: In dCloud environment, Jabber IM uses @dcloud.cisco.com while Webex environment uses @cbXXX.dc-YY.com
JABBER_DOMAIN = ""
WEBEX_DOMAIN = ""

# Folder to store the script logs and its run results
# If not changed: it will create a sub-folder of the current location called 'Logs'
LOGS_FOLDER = os.path.dirname(os.path.realpath(__file__)) + '\\Logs\\'

# Folder to store the files being transferred from Jabber's external file-server to Webex as attachments
# If not changed: it will create a sub-folder of the current location called 'FileTransfer'
LOCAL_FILE_TRANSFER_FOLDER = os.path.dirname(os.path.realpath(__file__)) + '\\FileTransfer\\'