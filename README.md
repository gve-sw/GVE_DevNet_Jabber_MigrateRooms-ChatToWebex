# GVE_DevNet_Jabber_Migrate_Rooms_Chat_To_Webex
This code is built to show the ability to migrate Cisco Jabber's persistent chat and rooms to Webex. This is for environment with [Persistent Chat Rooms](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/jabber/12_8/cjab_b_feature-configuration-for-jabber-128/cjab_b_feature-configuration-for-jabber-128_chapter_010.html#CJAB_RF_P5B96C5D_00) are enabled. It will use read-only access to the [External Databases](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/cucm/im_presence/database_setup/12_5_1/cup0_b_database-setup-guide-1251su2/cup0_mp_edff2920_00_external-database-tables.html) configured for Jabber, read the list of rooms, users, and messages, then posts them to Webex using [Webex APIs](https://developer.webex.com/docs/api/getting-started).

![/IMAGES/overview_1.png](/IMAGES/overview_1.png)

### High-level Overview

![/IMAGES/overview_2.png](/IMAGES/overview_2.png)

A video showing a sample run of this prototype: [https://youtu.be/4xJe8KsRjZs](https://youtu.be/4xJe8KsRjZs)

## Contacts
* Rami Alfadel (ralfadel@cisco.com)
* Gerardo Chaves (gchaves@cisco.com)

## Solution Components
* Cisco Jabber 
* Webex
* Python

## Installation/Configuration

 1. Clone this Github repository into a local folder:  
   ```git clone [add github link here]```
    - For Github link: 
        In Github, click on the **Clone or download** button in the upper part of the page > click the **copy icon**  
        ![/IMAGES/giturl.png](/IMAGES/giturl.png)
    - Or simply download the repository as zip file using 'Download ZIP' button

 2. Access the folder **GVE_DevNet_Jabber_MigrateRooms-ChatToWebex**:  
   ```cd GVE_DevNet_Jabber_MigrateRooms-ChatToWebex```

 3. Make sure you have [Python](https://www.python.org/downloads/) installed
 
 4. Load up the required libraries from *requirments.txt* file:  
   ```pip install -r requirments.txt```
 
 5. Configure the configuration variables in ```config.py``` file:
      
    1. Start with setting up the Persesent Chat DB connection:
        - Check the DB types supported by [SQLAlchemy engine](https://docs.sqlalchemy.org/en/14/core/engines.html) and choose the right engine type matching Jabber's external DB's platform.
          ```python
          # Persistent Chat DB
          TC_DB_TYPE = "<db_type>"
          TC_DB_HOST = "<hostname_or_ip_address_here>"
          TC_DB_NAME = "tcmadb"
          TC_DB_USER = "<username_here>"
          TC_DB_PASSWORD = "<password_here>"
          ```
    2. Set up the boolean variable *INCLUDE_FILE_TRANSFER* to choose to include file transfer activity or not, which refers to message attachments. 
        - Following the [Managed File Transfer](https://www.cisco.com/c/en/us/td/docs/voice_ip_comm/cucm/im_presence/configAdminGuide/11_5_1/CUP0_BK_CE08159C_00_config-admin-guide-imp-1151/CUP0_BK_CE08159C_00_config-admin-guide-imp-1151_chapter_01011.html#CUP0_RF_M4EC1846_00) workflow if it's enabled in the environment.
          ```python
          INCLUDE_FILE_TRANSFER = False
          ```
        - If set to *True*, two other sets of connection variables need to be configured:  
          1. *Managed file transfer DB* connection:
              ```python
              # Managed file transfer DB
              MFT_DB_TYPE = "<db_type>"
              MFT_DB_HOST = "<hostname_or_ip_address_here>"
              MFT_DB_NAME = "mftadb"
              MFT_DB_USER = "<username_here>"
              MFT_DB_PASSWORD = "<password_here>"
              ```
          2. *Managed file-transfer Server* connection:
              ```python
              # File-transfer server details
              FILE_SERVER_HOST = '<hostname_or_ip_address_here>'
              FILE_SERVER_USER = '<username_here>'
              FILE_SERVER_PASSWORD = '<password_here>'
              ```
    3. Set up the boolean variable *CREATE_WEBEX_ROOMS* to choose to migrate the detected Jabber rooms to Webex, or just test the script's ability to read Jabber's chat data.
        - For best practice, keep this variable as *False* for the first run, to test the connectivity and make sure the right data is read and stored in the logs correctly.

        - If set to *True*, set up the variable *WEBEX_AUTH* to have [Webex Access Token](https://developer.webex.com/docs/api/getting-started) for the archiver user that will be creating the rooms and adding the users & creating the messages found in Jabber:
          ```python
          WEBEX_AUTH = 'Bearer <webex_user_token>'
          ```
        - Also if set to *True*, set up the boolean variable *CHECK_WEBEX_EXISTING_ROOMS* to choose if you want to check for existing Webex rooms with the same title as the detected Jabber room's title. Please note that for the existing rooms to be detected, the archiver user (who runs this script) is part of the rooms meant to be checked. If that's the case, you will get the option to migrate the room or skip it:
          
          ![/IMAGES/check_existing_room.png](/IMAGES/check_existing_room.png)
      
        - Also if set to True, and in case *Jabber's Chat IM address* domain used is different than the user's email domain used in *Webex*, set up the following two variables accordingly:
          ```python
          # Example: In dCloud environment, Jabber IM uses @dcloud.cisco.com while Webex environment uses @cbXXX.dc-YY.com
          JABBER_DOMAIN = ""
          WEBEX_DOMAIN = ""
          ```
    4. Set up the following two varibales to have the paths to two local folders to store:
        - If not changed, the script will create sub-folders in the same current location
        1. Logs generated by running this script:
            ```python
            LOGS_FOLDER = os.path.dirname(os.path.realpath(__file__)) + '\\Logs\\'
            ```
        2. Local folder to download file-transfer attachments from the remote server to be able to forward it to Webex:
            ```python
            LOCAL_FILE_TRANSFER_FOLDER = os.path.dirname(os.path.realpath(__file__)) + '\\FileTransfer\\'
            ```
        


## Usage

1- Start with setting up the right variables in ```config.py``` as explained above.  
2- Run the main script ```main.py```:  
* ```python main.py```

3- The script progress and logs will be printed to the console, alongside a generated timestamped-logs that will be inside the configured *LOGS_FOLDER*:  
- If *CREATE_WEBEX_ROOMS* was set to *False*, the generated log file will be named:  
``` [current_time] - Read chat only.log```
- If *CREATE_WEBEX_ROOMS* was set to *True*, two files will be generated:
  - The main log file will be named:  
  ``` [current_time] - Migrate chat to Webex.log```
  - Another json file will be generated, named:  
  ``` [current_time] - Webex json summary.json```   
  The goal of this file is to have the summary of the generated Webex data. And can be used in case a rollback of the migration process is needed. More details below.

4- [Optional] If the data generated to Webex was somehow unacceptable or unexpected, the script ```rollback_webex_rooms.py``` can be run that will rollback the created Webex rooms and users. As follows:  
    
  1. Ask the user for the file: ```Webex json summary.json``` that was generated by the last step:
  ![/IMAGES/ask_for_json_summary_file.png](/IMAGES/ask_for_json_summary_file.png)
  2. Once the right file is provided, a list of the generated rooms with its users will be displayed. And a question will be asked to the user to confirm the rollback process:
  ![/IMAGES/confirm_to_delete_rooms.png](/IMAGES/confirm_to_delete_rooms.png)
  3. If the answer was yes, the created Webex rooms should have its added users removed. After that, a question will be shown to the user to decide if to leave the rooms as well:
  ![/IMAGES/confirm_to_leave_rooms.png](/IMAGES/confirm_to_leave_rooms.png)

5- [Optional] If the data generated to Webex was acceptable and the archiver user (who migrated the rooms to Webex) needs to leave the generated rooms, the script ```leave_webex_rooms.py``` can be run for the archiver user to leave the generated rooms.  
    
  - Warning! If the user left the generated rooms, you will no longer be able to rollback the created rooms through these scripts. Unless a [Compliance Officer role](https://developer.webex.com/docs/api/guides/compliance#compliance) was provided and an [Integration](https://developer.webex.com/docs/integrations) was created to do the rollback activity.

# Screenshots
A sample of a migrated message from Jabber to Webex that was [formatted with Markdown](https://developer.webex.com/docs/api/basics#formatting-messages):
![/IMAGES/sample_archived_message.png](/IMAGES/sample_archived_message.png)

![/IMAGES/overview_3.png](/IMAGES/overview_3.png)

### LICENSE

Provided under Cisco Sample Code License, for details see [LICENSE](LICENSE.md)

### CODE_OF_CONDUCT

Our code of conduct is available [here](CODE_OF_CONDUCT.md)

### CONTRIBUTING

See our contributing guidelines [here](CONTRIBUTING.md)

#### DISCLAIMER:
<b>Please note:</b> This script is meant for demo purposes only. All tools/ scripts in this repo are released for use "AS IS" without any warranties of any kind, including, but not limited to their installation, use, or performance. Any use of these scripts and tools is at your own risk. There is no guarantee that they have been through thorough testing in a comparable environment and we are not responsible for any damage or data loss incurred with their use.
You are responsible for reviewing and testing any scripts you run thoroughly before use in any non-testing environment.