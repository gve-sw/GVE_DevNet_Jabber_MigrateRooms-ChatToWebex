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
import requests
from sqlalchemy import create_engine
from lxml import etree                                                                               
import json
import time
import paramiko
import logging
import datetime
from pathlib import Path
from requests_toolbelt.multipart.encoder import MultipartEncoder

# Importing the connection variables: Jabber External DBs, Webex's Auth, and file_transfer server information
from config import LOGS_FOLDER, LOCAL_FILE_TRANSFER_FOLDER
from config import TC_DB_TYPE, TC_DB_HOST, TC_DB_NAME, TC_DB_USER, TC_DB_PASSWORD
from config import MFT_DB_TYPE, MFT_DB_HOST, MFT_DB_NAME, MFT_DB_USER, MFT_DB_PASSWORD
from config import WEBEX_AUTH, CREATE_WEBEX_ROOMS, CHECK_WEBEX_EXISTING_ROOMS
from config import INCLUDE_FILE_TRANSFER, FILE_SERVER_HOST, FILE_SERVER_USER, FILE_SERVER_PASSWORD

# Importing Jabber domain and Webex domain, in case they are different
from config import JABBER_DOMAIN, WEBEX_DOMAIN

# Setting up logging time to write new logs each time the script is run.
now = str(datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))

# Creating Logs folder, if it doesn't exist
if (not Path(LOGS_FOLDER).exists()):
    Path(LOGS_FOLDER).mkdir()

# Global variable to save Webex generated data in JSON format
global webex_json_data
global webex_room_dict
global webex_room_users

# If the user will migrate the rooms to Webex, the log file will be named: 'Migrate chat to Webex',
# and will create another log 'Webex generated rooms' and a json file 'Webex json summary' storing the activities done in Webex.
# Otherwise if the script is run to only read Jabber's data, the log file will be named: 'Read chat only'
if(CREATE_WEBEX_ROOMS):
    logging.basicConfig(filename=LOGS_FOLDER + now + ' - Migrate chat to Webex.log', level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%Y/%m/%d %I:%M:%S')
    webex_json_summary = logging.getLogger('Webex JSON summary')
    webex_json_summary.addHandler(logging.FileHandler(LOGS_FOLDER + now + ' - Webex json summary.json'))
    webex_json_summary.setLevel(level=logging.INFO)
    webex_json_data = []
    webex_room_dict = {}
    webex_room_users = []
    
else:
    logging.basicConfig(filename=LOGS_FOLDER + now + ' - Read chat only.log', level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%Y/%m/%d %I:%M:%S')

# Displaying the output on the console
logging.getLogger().addHandler(logging.StreamHandler())
logging.info("-"*25 + " Started " + "-"*25)

# Setting SQLALchemy engine to connect to Jabber external databases
tc_engine = create_engine(TC_DB_TYPE + '://' + TC_DB_USER +
                          ':' + TC_DB_PASSWORD + '@' + TC_DB_HOST + '/' + TC_DB_NAME)

if(INCLUDE_FILE_TRANSFER):
    mft_engine = create_engine(MFT_DB_TYPE + '://' + MFT_DB_USER +
                            ':' + MFT_DB_PASSWORD + '@' + MFT_DB_HOST + '/' + MFT_DB_NAME)

# Main function having the full script to read Jabber's persistent chat from External DB.
# And create the rooms, with their list of users, and messaages to Webex using its APIs
def main():
    global webex_json_data
    global webex_room_dict
    global webex_room_users
    # Connection to DB
    try:
        # Connect to persistance Chat DB
        conn = tc_engine.connect()
        logging.info('Completed connection to Persistant Chat DB')

        # Connect to Managed File Transfer DB
        if(INCLUDE_FILE_TRANSFER):
            conn_mft = mft_engine.connect()
            logging.info('Completed connection to Managed File Transfer DB')
    except:
        logging.info(
            'Error: Unable to connect to Jabber\'s external DBs for chat and file_transfer logs..')
        exit()

    # Connection to File Transfer Server
    # current_connection variable to keep the latest connection up, to deal with multiple file_server hosts
    if(INCLUDE_FILE_TRANSFER):
        current_connection = FILE_SERVER_HOST
        ftp_client = connect_to_file_server(current_connection)

    # Getting the archiver details: ID & email, before going through the list of users.
    # To determine if the archiver needs to leave the room after adding the users and messages
    if(CREATE_WEBEX_ROOMS):
        archiver_info = webex_api_get_archiver_details()
        
        # If CHECK_WEBEX_EXISTING_ROOMS is set to True, get the list of existing Webex_rooms titles
        if(CHECK_WEBEX_EXISTING_ROOMS):
            webex_titles = webex_api_get_existing_rooms()

    # Jabber Rooms #
    # Execute a query to list all the available Jabber rooms in DB.
    # Add a 'where' condition to the sql command to only get specific rooms
    # Example:
    # jabber_rooms = conn.execute("SELECT room_jid FROM tc_rooms where room_jid=<room_jid_here>'")
    jabber_rooms = conn.execute("SELECT room_jid FROM tc_rooms")

    # Loop throught the list of rooms and treat each room separately
    num_of_rooms = 0
    for j_room in jabber_rooms:

        num_of_rooms += 1
        logging.info('#'*25 + ' Room-' + str(num_of_rooms) + ' ' + '#'*25)

        # Storing room details in variables: room_id, room_title, room_subject
        j_room_id = j_room[0]
        logging.info('Jabber Room ID: ' + j_room_id)
        j_room_title = ''

        # Execute a query to get Room details: Name/Title
        room_config = conn.execute(
            "SELECT config FROM tc_rooms where room_jid = '" + j_room_id + "'")
        room_config = room_config.fetchone()

        # Get the room title/name from config xml result from DB
        j_room_title = xml_get_jabber_room_title(room_config[0])

        # Webex API  - Room Creation #
        # Create a room in Webex matching Jabber room (Title)
        if(CREATE_WEBEX_ROOMS):
            # If the user wanted to check Webex exisiting rooms' titles
            if(CHECK_WEBEX_EXISTING_ROOMS):
                room_matched = False
                for w_title in webex_titles:
                    # Once a room with the same title is found in Webex, it will be skipped
                    if(w_title == j_room_title):
                        logging.info('A room with the title: \"' + j_room_title + '\" already exists in Webex!)')
                        room_matched = True
                        break
                # Hanlding the matched room title, 'continue' will skip a loop iteration and check the next room
                if(room_matched):
                    invalid_choice = True
                    skip_room = False
                    while(invalid_choice):
                        choice = input('Do you want to migrate it? [Enter M] (new room will be created on Webex)\nor skip it? [Enter S]\n')
                        if choice in ['m','M']:
                            logging.info('Migrating this room ...')
                            invalid_choice = False
                        elif choice  in ['s','S']:
                            logging.info('Skipping this room')
                            invalid_choice = False
                            skip_room = True
                        else:
                            logging.info('Incorrect choice,, please check your input')
                    if(skip_room):
                        continue
                        
            # Resetting the list of users
            webex_room_users = []
            w_room_id = webex_api_create_room(j_room_title)

        # Boolean to choose if the archiver user needs to leave the room after everything
        # Changed to False after creating a seprate script to leave all the rooms (leave_webex_rooms.py)
        # Change to True to make the user leave directly after creating it and adding users & messages
        leave_room = False

        # Jabber Users #
        # Execute a query to get list of users in the current room
        jabber_room_users = conn.execute(
            "SELECT real_jid, affiliation FROM tc_users where role='none' AND room_jid = '" + j_room_id + "'")

        # Dealing with the list of users in the room one by one
        logging.info('Users:')
        num_of_users = 0
        for j_user in jabber_room_users:
            num_of_users += 1
            j_user_id = str(j_user[0])
            j_user_affiliation = str(j_user[1])

            logging.info('\t' + str(num_of_users) + '- ' + j_user_id +
                  '\taffiliation: ' + j_user_affiliation)

            # Boolean variable 'isModerator' to be used in Webex API matching the role/affiliation in Jabber
            w_user_moderator = "false"
            if (j_user_affiliation == "admin" or j_user_affiliation == "owner"):
                w_user_moderator = "true"

            # This step is only needed if the domain of Jabber IM is different than Webex environment
            j_user_id = j_user_id.replace(JABBER_DOMAIN, WEBEX_DOMAIN)

            # Checking if the archiving user in Webex was already a user in the room in Jabber
            if(CREATE_WEBEX_ROOMS):
                if (j_user_id == archiver_info["email"]):
                    leave_room = False

            # Webex API  - Adding Users to the Room #
            # Add the users in the newly created Webex room
            if(CREATE_WEBEX_ROOMS):
                webex_api_add_user_to_room(w_room_id, j_user_id, w_user_moderator)

        # Jabber Messages #
        # Execute a query to read messages details in the room from tc_msgarchive table
        jabber_messages = conn.execute(
            "SELECT sent_date, from_jid, body_string, message_string FROM tc_msgarchive where to_jid = '" + j_room_id + "'")

        # Printing the list of messaages in the room
        logging.info('Messages:')
        num_of_msgs = 0
        for j_msg in jabber_messages:
            num_of_msgs += 1
            j_msg_sent_date = str(j_msg[0])
            j_msg_sender_id = str(j_msg[1])
            j_msg_body = str(j_msg[2])
            j_msg_full_string = str(j_msg[3])

            logging.info('\t' + str(num_of_msgs) + '- sent_date: ' +
                  j_msg_sent_date + '\t from_jid: ' + j_msg_sender_id + '\n\t\tbody_string: ' + j_msg_body)

            # This step is only needed if the domain of Jabber IM is different than Webex environment
            j_msg_sender_id = j_msg_sender_id.replace(
                JABBER_DOMAIN, WEBEX_DOMAIN)

            # Trim the send_date to show only down to seconds, and match the managed file transfer DB's timing format
            j_msg_sent_date = j_msg_sent_date[0:19]

            # Checking if file_transfer is enabled, to connect to Managed File Transfer DB and File_Server
            if(INCLUDE_FILE_TRANSFER):
                # Detecting a text message with no attachments
                if (j_msg_body != 'Your chat application does not support downloading this file'):
                    # Formatting message text content & look using markdown, to show as an archived message
                    msg_txt_content = markdown_msg_text_for_webex(
                        j_msg_sender_id, j_msg_sent_date, j_msg_body)

                    # Webex API  - Creating the existing Jabber messages to the room #
                    # Create the list of Jabber messages in the newly created Webex room
                    if(CREATE_WEBEX_ROOMS):
                        webex_api_post_message_to_room(w_room_id, msg_txt_content)

                # A message that has attachment/s
                else:
                    logging.info('\tAttachment found! Getting file_Transfer details:')

                    # Parsing the xml result to get the file details from the DB field: message_string
                    file_name = xml_get_jabber_attachment_file_name(
                        j_msg_full_string)
                    attachment_text = xml_get_jabber_attachment_text(
                        j_msg_full_string)
                    file_server = ''
                    file_remote_path = ''

                    # Getting file details from the Managed File Transfer db, aft_log table. Matching:
                    # 1- The destiantion room, 2- The time of the message (up to the second), and 3- the file_name matching real_file_name
                    mft_file_details = conn_mft.execute("SELECT file_server, file_path, bytes_transferred FROM aft_log where method = 'Post' AND to_jid = '" +
                                                        j_room_id + "' AND timestampvalue = '" + j_msg_sent_date + "' AND real_filename = '" + file_name + "'")

                    mft_file_details = mft_file_details.fetchone()

                    # If there is no records on File_transfer_DB with the exact timestamp (down to the second),
                    # try to find the record with the same file name and destination room but close to its timestamp (Rounding up to x seconds)
                    if(mft_file_details is None):
                        logging.info('\tNo records for any file_transfer at: ' +
                            j_msg_sent_date)

                        # Finding the closest record to it in a +/-3 seconds range
                        logging.info(
                            '\tTrying to find the closest record with down to -3 seconds to it:')
                        x = 1
                        while((mft_file_details is None) and x <= 3):
                            msg_time_variable = datetime.datetime.strptime(
                                j_msg_sent_date, '%Y-%m-%d %H:%M:%S')
                            # Substract x seconds then check if the record was found
                            msg_time_variable = msg_time_variable + \
                                datetime.timedelta(seconds=-x)
                            logging.info('\tSearching for: ' + str(msg_time_variable))
                            mft_file_details = conn_mft.execute("SELECT file_server, file_path FROM aft_log where method = 'Post' AND to_jid = '" +
                                                                j_room_id + "' AND timestampvalue = '" + str(msg_time_variable) + "' AND real_filename = '" + file_name + "'")
                            mft_file_details = mft_file_details.fetchone()
                            # Attachment record found
                            if(mft_file_details is not None):
                                logging.info('\tRecord found! Forwarding the attachment..')
                            x += 1
                        # Reset the seconds, to go over search for x seconds up
                        x = 1
                        if(mft_file_details is None):
                            logging.info(
                                '\tNo recored. Trying to find the closest record with up to +3 seconds to it:')
                            while((mft_file_details is None) and x <= 3):
                                msg_time_variable = datetime.datetime.strptime(
                                    j_msg_sent_date, '%Y-%m-%d %H:%M:%S')
                                # Add x seconds then check if the record was found
                                msg_time_variable = msg_time_variable + \
                                    datetime.timedelta(seconds=x)
                                logging.info('\tSearching for: ' + str(msg_time_variable))
                                mft_file_details = conn_mft.execute("SELECT file_server, file_path FROM aft_log where method = 'Post' AND to_jid = '" +
                                                                    j_room_id + "' AND timestampvalue = '" + str(msg_time_variable) + "' AND real_filename = '" + file_name + "'")
                                mft_file_details = mft_file_details.fetchone()
                                # Attachment record found
                                if(mft_file_details is not None):
                                    logging.info('\tRecord found! Forwarding the attachment..')
                                x += 1

                    # After trying the time range for records and still not finding any results, skipping the message
                    if(mft_file_details is None):
                        logging.info('No records for any file_transfer at: ' +
                            j_msg_sent_date + ' or +/-3 around it')

                        # Skip the message and just post a notification about it
                        logging.info('\t\tPosting alert about the message to Webex:')
                        msg_txt_content = "(Archived message with attachment. Error: Unable to load file: Transfer record not found..)\\n**From: <@personEmail:" + \
                            j_msg_sender_id + ">**\\t```at: " + j_msg_sent_date + "```\\n" + attachment_text
                        if(CREATE_WEBEX_ROOMS):
                            webex_api_post_message_to_room(w_room_id, msg_txt_content)

                    # File found, save it to the temp folder, then forward it to Webex as an attachment
                    else:
                        file_server = str(mft_file_details[0])
                        file_remote_path = str(mft_file_details[1])
                        file_size = mft_file_details[2]
                        logging.info('Attachment location:\n\t\tServer: ' +
                            file_server + '\n\t\tRemote path: ' + file_remote_path)
                        logging.info('\t\tFile Size in bytes: ' + str(file_size))

                        # Checking if attachment size in not above the limit of Webex attachments of 100MB
                        if(file_size >= 100000000):
                            logging.info(
                                'File size is over the limit of Webex message attachments (100MB)')
                            logging.info('\t\tPosting alert about the message to Webex:')
                            msg_txt_content = "(Archived message with attachment. Error: Unable to load file: File size is too big..)\\n**From: <@personEmail:" + \
                                j_msg_sender_id + ">**\\t```at: " + j_msg_sent_date + "```\\n" + attachment_text
                            if(CREATE_WEBEX_ROOMS):
                                webex_api_post_message_to_room(w_room_id, msg_txt_content)

                        else:
                            # Save the file to a local_folder, then attach it in to Webex API call to create_message with attachment
                            logging.info('\t\tDownloading to: ' +
                                LOCAL_FILE_TRANSFER_FOLDER + file_name)
                            check_local_folder(LOCAL_FILE_TRANSFER_FOLDER)

                            # Check that the file_Server is matching the already connected ssh_client, otherwise reconnect to the newly found host
                            if (file_server == current_connection):
                                ftp_client.get(file_remote_path,
                                            (LOCAL_FILE_TRANSFER_FOLDER+file_name))
                                logging.info('\t\tFile downloaded..')
                            else:
                                logging.info(
                                    '\t\tFile_server found is different than current connection.. Switching the connection to: ' + file_server)
                                ftp_client = connect_to_file_server(file_server)
                                current_connection = file_server
                                ftp_client.get(file_remote_path,
                                            (LOCAL_FILE_TRANSFER_FOLDER+file_name))
                                logging.info('\t\tFile downloaded..')

                            # Webex API - Posting the message with attachments to the Webex room
                            if(CREATE_WEBEX_ROOMS):
                                webex_api_post_msg_with_attachment_to_room(w_room_id, j_msg_sender_id, j_msg_sent_date, attachment_text, (LOCAL_FILE_TRANSFER_FOLDER+file_name))

            # INCLUDE_FILE_TRANSFER is False,, just read text messages as they are
            else:
                # Formatting message text content & look using markdown, to show as an archived message
                    msg_txt_content = markdown_msg_text_for_webex(
                        j_msg_sender_id, j_msg_sent_date, j_msg_body)

                    # Webex API  - Creating the existing Jabber messages to the room #
                    # Create the list of Jabber messages in the newly created Webex room
                    if(CREATE_WEBEX_ROOMS):
                        webex_api_post_message_to_room(w_room_id, msg_txt_content)

        # After creating the room, adding the users, & posting the messages: record the room info & leave the room
        if(CREATE_WEBEX_ROOMS):
            # Recording webex generated data
            webex_room_dict["room_users"] = webex_room_users
            webex_json_data.append(webex_room_dict)
            # Leave the room if not originally part of it
            if(leave_room):
                webex_api_leave_room(w_room_id, archiver_info["id"])
    
    # Closing all connections
    conn.close()
    if(INCLUDE_FILE_TRANSFER):
        conn_mft.close()
        ftp_client.close()

    logging.info("-"*25 + " Completed " + "-"*25)
    if(CREATE_WEBEX_ROOMS):
        webex_json_summary.info((json.dumps(webex_json_data, indent=4)))

# pathlib - Check if the given folder exists, otherwise create it
def check_local_folder(folder_path):
    try:
        # The folder doesn't exist, create it
        if (not Path(folder_path).exists()):
            logging.info('Folder: ' + folder_path + ' doesn\'t exist. Creating it...')
            Path(folder_path).mkdir()
            logging.info('Folder created!')
    except:
        logging.info('Error: Unable to create the folder to transfer files..')
        exit()

# paramiko - Create an ftp_connection to a remote file server. To be able to get/put files from/to it.
def connect_to_file_server(file_server):
    try:
        # Connect to the file_server using SSH
        ssh_client = paramiko.SSHClient()
        # Policy for automatically adding the hostname and new host key to the local HostKeys object, and saving it
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(file_server, username=FILE_SERVER_USER,
                           password=FILE_SERVER_PASSWORD)
        logging.info('Completed connection to Managed File Transfer Server: ' + file_server)

        # Using SFTP client for file transfer of message attachments
        ftp_client = ssh_client.open_sftp()
        return ftp_client
    except:
        logging.info('Error: Unable to connect to Jabber\'s external file_transfer: ' +
              file_server + ' to retrieve message attachments..')
        exit()

# Webex API - Getting user details: ID & emails. Using People APIs
def webex_api_get_archiver_details():
    try:
        archiver_info = {"id": "", "email": ""}
        url = "https://webexapis.com/v1/people/me"
        payload = {}
        headers = {
            'Authorization': WEBEX_AUTH
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        res_dict = json.loads(response.text)
        archiver_info["id"] = res_dict["id"]
        archiver_info["email"] = res_dict["emails"][0]
        logging.info("Archiver_email: " + archiver_info["email"])
        json_element = {"archiver_user":archiver_info}
        webex_json_data.append(json_element)
        return archiver_info
    except:
        logging.info('Error getting Webex\'s archiver user details..')
        exit()

# Webex API - Getting existing rooms' titles details as a list. Using Rooms APIs
def webex_api_get_existing_rooms():
    w_rooms_titles = []
    # List the existing webex rooms
    logging.info('-' * 5 + ' Calling Webex API to list the existing rooms: ' + '*'*10)
    url = "https://webexapis.com/v1/rooms"
    payload = {}
    headers = {
        'Authorization': WEBEX_AUTH
    }
    response = requests.request("GET", url, headers=headers, data=payload)
    print("\tResponse Code:" + str(response.status_code) +
        ' (' + response.reason + ')')

    res_dict = json.loads(response.text)
    webex_rooms = res_dict["items"]
    logging.info('\nWebex existing rooms:')
    i = 0
    for w_room in webex_rooms:
        w_room_title = w_room["title"]
        w_room_type = w_room["type"]
        if(w_room_type == 'group'):
            i += 1
            logging.info(str(i) + '- \tType: ' + w_room_type + '\tTitle: ' + w_room_title)
            w_rooms_titles.append(w_room_title)
    return w_rooms_titles

# Webex API - Creating a new room with a given title. Using Rooms APIs
def webex_api_create_room(room_title):
    global webex_json_data
    global webex_room_dict
    global webex_room_users
    try:
        logging.info('-' * 5 + ' Calling Webex API to create Room: ' +
              room_title)
        url = "https://webexapis.com/v1/rooms"
        payload = {
            "title": room_title
        }
        headers = {
            'Authorization': WEBEX_AUTH
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        logging.info("\tResponse Code:" + str(response.status_code) +
              ' (' + response.reason + ')')

        # Handling failed requests
        if(response.status_code == 401):
            logging.info(
                'Webex authentication credentials are missing or incorrect..')
            exit()
        while(response.status_code == 429):
            logging.info('Too many requests have been sent in a given amount of time...')
            res_dict = json.loads(response.text)
            retry_after = res_dict["Retry-After"]
            logging.info('Retrying after: ' + str(retry_after) + " seconds")
            time.sleep(retry_after)
            response = requests.request(
                "POST", url, headers=headers, data=payload)

        # Saving the created Webex room_id
        res_dict = json.loads(response.text)
        w_room_id = res_dict["id"]

        # Recording webex generated data
        logging.info("Created Webex's Room with ID: " + w_room_id)
        logging.info("-"*30 + "\nCreated Webex's Room with ID: " + w_room_id)
        logging.info("\tTitle: " + room_title)
        json_room_details = {"title":room_title,"id":w_room_id}
        webex_room_dict = {"webex_room":json_room_details}

        return w_room_id
    except:
        logging.info('Error: Unable to create Webex room..')
        exit()

# Webex API - Adding a new user to a room, with choosing if moderator or not. Using Memberships APIs
def webex_api_add_user_to_room(room_id, user_email, is_moderator):
    global webex_json_data
    global webex_room_dict
    global webex_room_users
    try:
        logging.info('-' * 5 + ' Calling Webex API to add the user: ' +
              user_email)
        url = "https://webexapis.com/v1/memberships"
        payload = "{\"isModerator\": \"" + is_moderator + "\",\"personEmail\": \"" + user_email + \
            "\",\"roomId\": \"" + room_id + "\"}"
        headers = {
            'Authorization': WEBEX_AUTH,
            'Content-Type': 'application/json'
        }
        response = requests.request(
            "POST", url, headers=headers, data=payload)
        logging.info("\tResponse Code: " + str(response.status_code) +
              ' (' + response.reason + ')')
        res_dict = json.loads(response.text)
        if(response.status_code == 409):
            logging.info('\tWarning: User already exists..')
            json_user_details = {"user_already_exists":"true", "email":user_email, "idModerator":is_moderator}
            webex_room_users.append(json_user_details)
        else:
            w_user_id = res_dict["personId"]

            # Recording webex generated data
            logging.info("\t\tAdded User with ID: " + w_user_id)
            logging.info("\t\t\tEmail: " + user_email)
            json_user_details = {"email":user_email, "idModerator":is_moderator, "id":w_user_id}
            webex_room_users.append(json_user_details)

        # Handling failed requests
        if(response.status_code == 401):
            logging.info(
                'Webex authentication credentials are missing or incorrect.\nEnding application...')
            exit()
        while(response.status_code == 429):
            logging.info('Too many requests have been sent in a given amount of time...')
            res_dict = json.loads(response.text)
            retry_after = res_dict["Retry-After"]
            logging.info('Retrying after: ' + str(retry_after) + " seconds")
            time.sleep(retry_after)
            response = requests.request(
                "POST", url, headers=headers, data=payload)
    except:
        logging.info('Error adding user: ' + user_email + ' to the room..')

# Webex API - Deleting a user from a room. Won't be possible if the user is the only moderator. Using Memberships APIs
def webex_api_leave_room(room_id, user_id):
    try:

        # Getting the membershipId for the archiver user in the room, to leave it if needed
        logging.info('-' * 5 + ' Calling Webex API to get membership Id of Archiver')
        url = "https://webexapis.com/v1/memberships" + "?roomId=" + \
            room_id + "&personId=" + user_id
        headers = {
            'Authorization': WEBEX_AUTH,
            'Content-Type': 'application/json'
        }
        payload = {}
        response = requests.request(
            "GET", url, headers=headers, data=payload)
        logging.info("\tResponse Code: " + str(response.status_code) +
              ' (' + response.reason + ')')
        res_dict = json.loads(response.text)
        membership_id = res_dict["items"][0]["id"]

        # Leaving the room by calling DELETE membershipId
        logging.info('-' * 5 + ' Calling Webex API to delete archiver from the room')
        url = "https://webexapis.com/v1/memberships" + "/" + membership_id
        payload = {}
        response = requests.request(
            "DELETE", url, headers=headers, data=payload)
        logging.info("\tResponse Code: " + str(response.status_code) +
              ' (' + response.reason + ')')
        logging.info("%"*5 + " Archiver user leaving the room")
    except:
        logging.info('Error deleting user(archiver) from the room ..')

# Webex API - Posting a message to a room. Using Messages APIs
def webex_api_post_message_to_room(room_id, msg_txt_content):
    try:
        logging.info('-' * 5 + ' Calling Webex API to add the message to the room')

        url = "https://webexapis.com/v1/messages"
        headers = {
            'Authorization': WEBEX_AUTH,
            'Content-Type': 'application/json'
        }
        payload = "{\"roomId\": \"" + room_id + \
            "\", \"markdown\": \"" + msg_txt_content + "\"}"
        response = requests.request(
            "POST", url, headers=headers, data=payload)
        logging.info("\tResponse Code: " + str(response.status_code) +
              ' (' + response.reason + ')')

        # Handling failed requests
        if(response.status_code == 401):
            logging.info(
                'Webex authentication credentials are missing or incorrect.\nEnding application...')
            exit()
        while(response.status_code == 429):
            logging.info(
                'Too many requests have been sent in a given amount of time...')
            res_dict = json.loads(response.text)
            retry_after = res_dict["Retry-After"]
            logging.info('Retrying after: ' + str(retry_after) + " seconds")
            time.sleep(retry_after)
            response = requests.request(
                "POST", url, headers=headers, data=payload)
    except:
        logging.info('Error posting message: ' + msg_txt_content + ' to the room..')

# Webex API - Posting a message with attachment to a room. Using Messages APIs
def webex_api_post_msg_with_attachment_to_room(w_room_id, j_msg_sender_id, j_msg_sent_date, attachment_text, file_path):
    logging.info('-' * 5 + ' Calling Webex API to add the message with attachment')

    msg_txt_content = "(Archived message with attachment)\n**From: <@personEmail:" + \
        j_msg_sender_id + ">**\t```at: " + j_msg_sent_date + "```\n" + attachment_text
    payload = MultipartEncoder({'roomId': w_room_id, 'markdown': msg_txt_content, 'files': (
        file_path, open(file_path, 'rb'))})

    url = "https://webexapis.com/v1/messages"
    headers = {
        'Authorization': WEBEX_AUTH,
        'Content-Type': payload.content_type
    }
    response = requests.request(
        "POST", url, headers=headers, data=payload)
    logging.info("\tResponse Code: " + str(response.status_code) +
          ' (' + response.reason + ')')

# lxml - Parsing an XML string to get file name inside a advanced-file-transfer element
def xml_get_jabber_attachment_file_name(msg_string_xml):
    # Getting filename from a similar xml structure of:
    '''
    <message ... >
        <advanced-file-transfer ... >
            ...
            <filename>result_here</filename>
            ...
        </advanced-file-transfer>
    </message>
    '''
    xml_root = etree.fromstring(msg_string_xml)

    # Going through the xml tree to find the <advanced-file-transfer> element to get: <filename> from it
    aft_element = ''
    for element in xml_root:
        if('advanced-file-transfer' in element.tag):
            aft_element = element

    # From the XML tree, get the file_name and URL
    for sub_element in aft_element:
        if('filename' in str(sub_element.tag)):
            file_name = str(sub_element.text)
            logging.info('\t\tfile_name: ' + file_name)

    return file_name

# lxml - Parsing an XML string to get a message that is written alongside an attachment file
def xml_get_jabber_attachment_text(msg_string_xml):
    # Getting a message that is written with an attachment file from a similar xml structure of:
    '''
    <message ... >
        ...
        <aft-html ... >
            <body ... >
                <span ... >
                    <div>
                        result_here
                        <div ...>
                        </div>
                    </div>
                </span>
            </body>
        </aft-html>
    </message>
    '''

    xml_root = etree.fromstring(msg_string_xml)
    attachment_text = ''

    # Going through the xml tree to find the <aft-html> element to get the text sent with the attachment
    aft_html_element = ''
    for element in xml_root:
        if('aft-html' in element.tag):
            aft_html_element = element

    # From the XML tree, get the text included with attachements; if it exists
    for body_element in aft_html_element:
        if('body' in str(body_element.tag)):
            for span_element in body_element:
                if('span' in str(span_element.tag)):
                    for div_element in span_element:
                        attachment_text = " ".join(
                            t for t in div_element.xpath("text()"))
                        logging.info('\t\tText with the attachment: ' +
                              attachment_text)

    return attachment_text

# lxml - Parsing the output of Jabber room's config' field, and getting the Room Name/Title
def xml_get_jabber_room_title(config_xml):
    # Getting Room name from a similar xml structure of:
    '''
    <x ... >
        <field ...>
            <value>...</value>
        <field ... var='muc#roomconfig_roomname'>
            <value>result_here</value>
        <field>
    </x>
    '''
    xml_root = etree.fromstring(config_xml)

    # Get the room name/title from the XML output of 'config' field which is the value of the third element:
    # i.e: ... <field type='text-single' var='muc#roomconfig_roomname'><value>ROOM_NAME</value> ...
    for element in xml_root:
        if('\'muc#roomconfig_roomname\'' in str(element.attrib)):
            for sub_element in element:
                j_room_title = str(sub_element.text)

    logging.info('Jabber Room Title: ' + j_room_title)
    return j_room_title

# Python String Manipulation - Formatting the message to be sent to Webex to follow markdown markup language
def markdown_msg_text_for_webex(msg_sender_id, msg_sent_date, msg_body):
    # Formatting the message content to have an archived look similar to:
    '''
    (Archived message)
    From: User at: 20xx-0x-0x xx:xx:xx
    Hello in Jabber!
    '''
    # Handling messages with special characters, to be posted to Webex as is
    msg_body = str(repr(msg_body))

    # Removing single quotes (1st and last letters) resulted from 'repr' method
    msg_body = msg_body[1:]
    msg_body = msg_body[:-1]

    # Messages with new lines
    msg_body = msg_body.replace('\\n', '\\n')

    # Messages with quotations
    msg_body = msg_body.replace('\"', '\\\"')

    msg_txt_content = "(Archived message)\\n**From: <@personEmail:" + \
        msg_sender_id + ">**\\t```at: " + msg_sent_date + "```\\n" + msg_body

    return msg_txt_content


main()
