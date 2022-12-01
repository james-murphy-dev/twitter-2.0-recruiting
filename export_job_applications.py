import base64
import hashlib
import os
import re
import json
import requests
import datetime
import dateutil.parser
import gspread
from requests_oauthlib import OAuth2Session
from urlextract import URLExtract
from urllib.parse import urlsplit, urlunsplit
import requests

from google.oauth2 import service_account

# This example is set up to retrieve Direct Message events of the authenticating user. This supports both
# one-to-one and group conversations.
GET_DM_EVENTS_URL = "https://api.twitter.com/2/dm_events"
GET_USER_PROFILE_URL = "https://api.twitter.com/2/users" #/:id

#-----------------------------------------------------------------------------------------------------------------------
# These variables need to be updated to the setting that match how your Twitter App is set-up at
# https://developer.twitter.com/en/portal/dashboard. These will not change from run-by-run.
client_id = "ckhLX2dqSHFON3pFVUFXMTV5NHg6MTpjaQ"
#client_secret = "83BVjTKpDGrkmn3CYRDqrgsa2r2yUJW9MBpVjC0LoQMIMofpXl"
#This must match *exactly* the redirect URL specified in the Developer Portal.
redirect_uri = "https://www.twitter.com/"
#-----------------------------------------------------------------------------------------------------------------------

'''
GOOGLE SHEETS
'''
SPREADSHEET_NAME = "Twitter 2.0 recruiting"
ENG_SHEET_NAME = "Engineering"
DESIGN_SHEET_NAME = "Design"

COL_USERNAME = "Username"
COL_EMAILS =  "Email(s)"
COL_LINKEDIN = "LinkedIn"
COL_GITHUB = "GitHub links"
COL_OTHER_LINKS = "Other links"
COL_MESSAGES = "DM contents"
COL_ATTACHMENTS = "Attachment(s)"
COL_STATUS = "Status"

SHEET_COLUMNS = [
    COL_USERNAME, COL_EMAILS, COL_LINKEDIN, COL_GITHUB, COL_OTHER_LINKS, COL_MESSAGES, COL_ATTACHMENTS, COL_STATUS    
]

'''
TWITTER
'''
# original date of job post
# https://twitter.com/growing_daniel/status/1596937433626865665
RECRUITMENT_TWEET_TIME = "2022-11-27T18:42:00.000Z"
cutoff_date = dateutil.parser.parse(RECRUITMENT_TWEET_TIME)

# recgonized hostnames, feel free to add more
LINKEDIN_HOSTNAME = "https://linkedin.com/"
GITHUB_HOSTNAME = "https://github.com/"

known_links = [LINKEDIN_HOSTNAME, GITHUB_HOSTNAME]
minimum_link_count = 1 # complete submissions need at least 1 non-LinkedIn link

# recognized keywords
languages = ["C", "C++", "C#", "R", "Go", "Golang", "Java", "JavaScript", "HTML", "CSS", "Kotlin", "Swift", "Python", "Ruby", "PHP", "Scala", "Rust"]
databases = ["SQL", "NoSQL", "MongoDB"]

user_table = {}
# each table entry contains (user_id, user_profile)
# user profile:
KEY_ROLES = 'roles' #string array
KEY_USERNAME = 'username' #string
KEY_LINKEDIN = 'linkedin' #string
KEY_GITHUB = 'github' #string
KEY_OTHER_LINKS = 'other_links' #string array
KEY_EMAILS = 'emails' #string array
KEY_MESSAGES = 'messages' #string array
KEY_ATTACHMENTS = 'attachments' #boolean
KEY_LINK_COUNT = 'links' #num
KEY_COMPLETE = 'complete' #boolean

# Twitter API
# DM events
KEY_TEXT = 'text'
KEY_SENDER = 'sender_id'

def handle_oauth():

    # Set the scopes needed to be granted by the authenticating user.
    scopes = ["dm.read", "tweet.read", "users.read", "offline.access"]

    # Create a code verifier.
    code_verifier = base64.urlsafe_b64encode(os.urandom(30)).decode("utf-8")
    code_verifier = re.sub("[^a-zA-Z0-9]+", "", code_verifier)

    # Create a code challenge.
    code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    code_challenge = base64.urlsafe_b64encode(code_challenge).decode("utf-8")
    code_challenge = code_challenge.replace("=", "")

    # Start an OAuth 2.0 session.
    oauth = OAuth2Session(client_id, redirect_uri=redirect_uri, scope=scopes)

    # Create an authorize URL.
    auth_url = "https://twitter.com/i/oauth2/authorize"
    authorization_url, state = oauth.authorization_url(
        auth_url, code_challenge=code_challenge, code_challenge_method="S256"
    )

    # Visit the URL to authorize your App to make requests on behalf of a user.
    print(
        "Visit the following URL to authorize your App on behalf of your Twitter handle in a browser:"
    )
    print(authorization_url)

    # Paste in your authorize URL to complete the request.
    authorization_response = input(
        "Paste in the full URL after you've authorized your App:\n"
    )

    # Fetch your access token.
    token_url = "https://api.twitter.com/2/oauth2/token"

    # The following line of code will only work if you are using a type of App that is a public client.
    auth = False

    
    token = oauth.fetch_token(
        token_url=token_url,
        authorization_response=authorization_response,
        auth=auth,
        client_id=client_id,
        include_client_id=True,
        code_verifier=code_verifier,
    )

    # The access token.
    access = token["access_token"]

    return access

def get_user_conversation_events(access, page = -1):

    headers = {
        "Authorization": "Bearer {}".format(access),
        "Content-Type": "application/json",
        "User-Agent": "TwitterDevSampleCode",
        "X-TFE-Experiment-environment": "staging1",
        "Dtab-Local": "/s/gizmoduck/test-users-temporary => /s/gizmoduck/gizmoduck"
    }

    request_url = GET_DM_EVENTS_URL

    # parameters, change as needed
    request_url+="?dm_event.fields=attachments,created_at,dm_conversation_id,event_type,id,participant_ids,referenced_tweets,sender_id,text"
    request_url+="&event_types=MessageCreate"
    if (page!=-1):
        request_url+=f"&pagination_token={page}"

    response = requests.request("GET", request_url, headers=headers)

    if response.status_code != 200:
        print("Request returned an error: {} {}".format(response.status_code, response.text))
    else:
        return response

def get_user_profile(access, id):

    headers = {
        "Authorization": "Bearer {}".format(access),
        "Content-Type": "application/json",
        "User-Agent": "TwitterDevSampleCode",
        "X-TFE-Experiment-environment": "staging1",
        "Dtab-Local": "/s/gizmoduck/test-users-temporary => /s/gizmoduck/gizmoduck"
    }

    request_url = GET_USER_PROFILE_URL+f"/{id}"
    response = requests.request("GET", request_url, headers=headers)

    if response.status_code != 200:
        print("Request returned an error: {} {}".format(response.status_code, response.text))
    else:
        print(f"Response code: {response.status_code}")
        body = json.loads(response.text)
        return body['data'][KEY_USERNAME]

def is_email(link):
    return re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", link)

def parse_links(dm):
    extractor = URLExtract(extract_email=True)
    links = extractor.find_urls(dm['text'], only_unique=True, with_schema_only=True)
    for link in links:
        r = requests.head(link, allow_redirects=True)

        split_url = urlsplit(r.url) # 'http://127.0.0.1/asdf/login.php?q=abc#stackoverflow'
    
        sender = dm[KEY_SENDER]

        if (user_table[sender][KEY_LINKEDIN] is None and split_url.hostname==LINKEDIN_HOSTNAME):
            # LinkedIn
            user_table[sender][KEY_LINKEDIN] = split_url.path
            # decide if you want to allow LinkedIn alone to complete a submission
            # user_table[sender]['links']+=1
        elif (split_url.hostname==GITHUB_HOSTNAME):
            # could be multiple GitHub links
            user_table[sender][KEY_GITHUB].append(split_url.path)
            user_table[sender][KEY_LINK_COUNT]+=1      
        elif (is_email(r.url)):
            # could be multiple email addresses
            user_table[sender][KEY_EMAILS].append(r.url)
        else:
            user_table[sender][KEY_OTHER_LINKS].append(r.url)
            user_table[sender][KEY_LINK_COUNT]+=1

def get_row_values(applicant):
    return [
        [
            applicant[KEY_USERNAME],
            "\n".join(applicant[KEY_EMAILS]),
            applicant[KEY_LINKEDIN],
            "\n".join(applicant[KEY_GITHUB]),
            "\n".join(applicant[KEY_OTHER_LINKS]),
            "\n".join(applicant[KEY_MESSAGES]),
            applicant[KEY_ATTACHMENTS]
        ]
    ]

def update_row(row, applicant, sheet):
    cell_range = f"A{row}:G{row}"
    values = get_row_values(applicant)
    sheet.update(cell_range, values)

def next_available_row(worksheet):
    str_list = list(filter(None, worksheet.col_values(1)))
    return str(len(str_list)+1)

def update_rows(sheet, profiles):
    
     # update rows with new data, create new rows for new submissions
    for applicant in profiles.values():
        # for each applicant, determine if there is an existing row
        applicant_username_cell = sheet.find(applicant[KEY_USERNAME])
        if (applicant_username_cell is not None):
            # if yes, update the row with any new data
            update_row(applicant_username_cell.row, applicant, sheet)
        else:
            # if no, create the row
            first_empty_row = next_available_row(sheet) #search for first empty cell
            data = get_row_values(applicant) # [ [1], [1], [1], [1], [1] ,[1] ,[1]] #
            cell_range = f"A{first_empty_row}:G{first_empty_row}"
            sheet.update(cell_range, data)
       
    return True

def update_sheet():
    # filter user_table for engineering applicants with complete submissions
    engineers = { key:value for (key, value) in user_table.items() if 'engineer' in value[KEY_ROLES] and value[KEY_COMPLETE] == True}
    designers = { key:value for (key, value) in user_table.items() if 'designer' in value[KEY_ROLES] and value[KEY_COMPLETE] == True}

    gc = gspread.oauth(flow=gspread.auth.console_flow)

    # if spreadsheet is already created, open the existing file
    try:
        workbook = gc.open(SPREADSHEET_NAME)
        eng_sheet = workbook.worksheet(ENG_SHEET_NAME)
        design_sheet = workbook.worksheet(DESIGN_SHEET_NAME)
    except:
        # create worksheets if the document is new
        workbook = gc.create(SPREADSHEET_NAME)
        workbook.del_worksheet()
        eng_sheet = workbook.add_worksheet(ENG_SHEET_NAME, len(engineers), len(SHEET_COLUMNS))
        design_sheet = workbook.add_worksheet(DESIGN_SHEET_NAME, len(designers), len(SHEET_COLUMNS))
        
        # remove default Sheet1
        sheet1 = workbook.get_worksheet(0)
        workbook.del_worksheet(sheet1)

        eng_sheet.update("A1:G1", [SHEET_COLUMNS])
    
    # remove default Sheet1
    sheet1 = workbook.get_worksheet(0)
    workbook.del_worksheet(sheet1)

    if (len(engineers)>0):
        update_rows(eng_sheet, engineers)
    if (len(designers)>0):
        update_rows(design_sheet, designers)

    print(f"View your new spreadsheet here: https://docs.google.com/spreadsheets/d/{workbook.id}")

    return True

def is_engineering_applicant(message):
    return 'engineer' in message.lower() or 'developer' in message.lower()

def is_design_applicant(message):
    # could potentially remove 'er' to catch more applicants
    return 'designer' in message.lower()

def create_user_profile(username):
    return {
        KEY_USERNAME : username,
        KEY_OTHER_LINKS : [],
        KEY_ROLES: [],
        KEY_EMAILS: [],
        KEY_LINKEDIN : None,
        KEY_GITHUB: [],
        KEY_MESSAGES: [],
        KEY_ATTACHMENTS: False,
        KEY_LINK_COUNT: 0,
        KEY_COMPLETE: False,
    }

def extract_user_profile(access, dm):

    sender = dm[KEY_SENDER]
    # identify user name
    if (not user_table.__contains__(sender)):
        username = get_user_profile(access, sender)
        # create new user object
        user_table[sender] = create_user_profile(username)

    # identify role(s) applying for
    if (is_engineering_applicant(dm['text'])):
        user_table[sender][KEY_ROLES].append("engineer")
    if (is_design_applicant(dm['text'])):
        user_table[sender][KEY_ROLES].append("designer")

    # identify links, match with user profile stored in hash table
    parse_links(dm)

    # add text contents of DM (cover letter/resume) to user profile 
    if (len(user_table[sender][KEY_MESSAGES]) > 0):
        # DMs are returned from API in reverse-chronological order, so prepend each one to the beginning of messages list
        user_table[sender][KEY_MESSAGES] = [dm['text']] + user_table[sender][KEY_MESSAGES]
    else:
        # TODO convert links to hyperlinks
        user_table[sender][KEY_MESSAGES] = [dm['text']]

    # check if applicant attached an image (resume, portfolio, etc.)
    if (user_table[sender][KEY_ATTACHMENTS] is None and dm[KEY_ATTACHMENTS] is not None):
        user_table[sender][KEY_ATTACHMENTS] = True

    # TODO scan message for potential keywords
    # languages, libraries, databases, SDKs, architectures
    
    # TODO scan message for years of experience
    # find 'years of experience' instances and insert highest number in user record

    # TODO add latest and earliest DM timestamps to user record for sorting

    # check if user profile is complete
    if (user_table[sender][KEY_LINK_COUNT] >= minimum_link_count):
        user_table[sender][KEY_COMPLETE] = True

def query_dms(access, page = -1):

    response = get_user_conversation_events(access, page)

    body = json.loads(response.text)

    # parse each message
    for dm in body['data']:
        dm_date = dateutil.parser.parse(dm['created_at'])
        if (dm_date < cutoff_date):
            # end of possible job applications reached
            print("end of possible job applications reached")
            update_sheet()
            return True
        else:
            extract_user_profile(access, dm)

    return query_dms(access, body['meta']['next_token'])

def main():
    access = handle_oauth()
    query_dms(access)
    
if __name__ == "__main__":
    main()
