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
import json
import logging
from config import WEBEX_AUTH, LOGS_FOLDER

# Global variable to store the information for the user running this script
global archiver_info


# Main function to run the script to leave Webex created rooms
def leave():
    global archiver_info
    
    json_file_name = input('Please enter (or paste) the file name of Webex Json Summary to leave generated rooms:\n')
    
    try:
        with open(LOGS_FOLDER + json_file_name) as f:
            json_data = json.load(f)
    except:
        logging.info('File failed to load. Please make sure of the file name and location')
        exit()
    
    # Setting up the logger to store the rollback process
    logging.basicConfig(filename=LOGS_FOLDER + json_file_name + ' -Leave.log', level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%Y/%m/%d %I:%M:%S')
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.info("-"*25 + " Started " + "-"*25)
    logging.info('File: '+ json_file_name)

    # Read the json file and display the summary of the data that was found
    display_found_rooms(json_data)
    
    # Getting the information for the user running this script
    archiver_info = webex_api_get_archiver_details()

    # After removing the users from the rooms, ask the archiver user if to leave the created rooms
    archiver_leaving_all_rooms(json_data)

    logging.info('-'*20 + ' Ending the application ' + '-'*20)

# Webex API - Getting user details: ID & emails. Using People APIs
def webex_api_get_archiver_details():
    global archiver_info
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
        return archiver_info
    except:
        logging.info('Error getting Webex\'s archiver user details..')
        exit()

# Read the json file and display the summary of the data that was found
def display_found_rooms(json_data):
    # logging.info('Data:\n' + str(json_data))
    num_of_rooms = 0
    for element in json_data:
        # logging.info('Element:' + str(element))
        if "webex_room" in element:
            num_of_rooms += 1
            logging.info('#'*5 + ' Room #' + str(num_of_rooms) + ': ' + element["webex_room"]["title"])

# Webex API - Removing a user from a room usingthe room Id and the user's email. Using Memberships APIs
def webex_api_remove_user_from_room(w_room_id, w_user_email):
    global archiver_info
    w_memb_id = ''
    logging.info('-'*3 + 'Calling Webex API to remove user: ' + w_user_email)

    # List the existing webex memberships
    logging.info('-'*3 + ' Calling Webex API to get the user\'s membership:')
    url = "https://webexapis.com/v1/memberships" + "?roomId=" + w_room_id + "&personEmail=" + w_user_email
    payload = {}
    headers = {
        'Authorization': WEBEX_AUTH
    }
    response = requests.request("GET", url, headers=headers, data=payload)
    logging.info("\tResponse Code:" + str(response.status_code) +
          ' (' + str(response.reason) + ')')

    res_dict = json.loads(response.text)
    webex_memberships = res_dict["items"]

    for w_memb in webex_memberships:
        w_memb_id = w_memb["id"]        

    if(w_memb_id == ''):
        logging.info('Membership not found. User is no longer part of the room..')
    else:
        # Delete a membership
        logging.info('-'*3 + ' Calling Webex API to delete the membership: ')
        url = "https://webexapis.com/v1/memberships" + "/" + w_memb_id
        payload = {}
        headers = {
            'Authorization': WEBEX_AUTH
        }
        response = requests.request("DELETE", url, headers=headers, data=payload)
        logging.info("\tResponse Code:" + str(response.status_code) +
          ' (' + str(response.reason) + ')')

# After removing the users from the rooms, ask the archiver user if to leave the created rooms
def archiver_leaving_all_rooms(json_data):
    global archiver_info

    invalid_choice = True
    leave_rooms = False
    while(invalid_choice):
        choice = input('Do you want to leave these rooms? [Y/N]\n')
        if choice in ['n','N']:
            logging.info('You\'ve chosen not to leave them .. ')
            logging.info('-'*20 + ' Ending the application ' + '-'*20)
            invalid_choice = False
            exit()
        elif choice in ['y','Y']:
            logging.info('Leaving the rooms ...')
            invalid_choice = False
            leave_rooms = True
        else:
            logging.info('Incorrect choice,, please check your input')
    if(leave_rooms):
        num_of_rooms = 0
        w_room_id = ''
        for element in json_data:
            if "webex_room" in element:
                num_of_rooms += 1
                logging.info('#'*5 + ' Room #' + str(num_of_rooms) + ': ' + element["webex_room"]["title"])
                w_room_id = element["webex_room"]["id"]
            if "room_users" in element:
                webex_api_remove_user_from_room(w_room_id,archiver_info["email"])

                
leave()