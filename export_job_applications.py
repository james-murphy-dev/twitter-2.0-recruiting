import base64
import hashlib
import os
import re
import json
import requests
import dateutil.parser
import configparser
from requests_oauthlib import OAuth2Session
from user_info import Profile
from user_info_constants import *
from api_resp_attrs.twitter import *
from keywords import is_job_applicant
import spreadsheet

config = configparser.ConfigParser()
config.read("config.ini")

client_id = config.get('TWITTER_API', 'client_id')
redirect_uri = config.get('TWITTER_API', 'REDIRECT_URI')

HOSTNAME_LINKEDIN = config.get('KNOWN_HOSTS', 'LINKEDIN')
HOSTNAME_GITHUB = config.get('KNOWN_HOSTS', 'GITHUB')

RECRUITMENT_TWEET_TIME = config.get('DATES', 'RECRUITMENT_TWEET')
cutoff_date = dateutil.parser.parse(RECRUITMENT_TWEET_TIME)

# each table entry contains (user_id, job_applicant)
user_table = {}

'''
Auth functions
'''
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

'''
Twitter API
'''
def get_user_conversation_events(access, page = -1):

    headers = {
        "Authorization": "Bearer {}".format(access),
        "Content-Type": "application/json",
        "User-Agent": "TwitterDevSampleCode",
        "X-TFE-Experiment-environment": "staging1",
        "Dtab-Local": "/s/gizmoduck/test-users-temporary => /s/gizmoduck/gizmoduck"
    }

    request_url = config.get('TWITTER_API', 'GET_DM_EVENTS')

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

    request_url = config.get('TWITTER_API', 'GET_USER_PROFILE')+f"/{id}"
    request_url += "?user.fields=name,profile_image_url"
    response = requests.request("GET", request_url, headers=headers)

    if response.status_code != 200:
        print("Request returned an error: {} {}".format(response.status_code, response.text))
    else:
        print(f"Response code: {response.status_code}")
        body = json.loads(response.text)
        return body['data']

def update_user_profile(access, dm):

    sender = dm[KEY_SENDER]
    # identify user name
    if (not user_table.__contains__(sender)):
        user = Profile()
    else:
        user = user_table[sender]

    user.parse_dm_info(dm)

    user_table[sender] = user

def get_user_profiles(access, profiles):
    headers = {
        "Authorization": "Bearer {}".format(access),
        "Content-Type": "application/json",
        "User-Agent": "TwitterDevSampleCode",
        "X-TFE-Experiment-environment": "staging1",
        "Dtab-Local": "/s/gizmoduck/test-users-temporary => /s/gizmoduck/gizmoduck"
    }

    ids = ",".join(list(profiles.keys()))
    request_url = config.get('TWITTER_API', 'GET_USER_PROFILE_BATCH') + f"/?ids={ids}"
    request_url += "&user.fields=name,profile_image_url"
    response = requests.request("GET", request_url, headers=headers)

    if response.status_code != 200:
        print("Request returned an error: {} {}".format(response.status_code, response.text))
    else:
        print(f"Response code: {response.status_code}")
        body = json.loads(response.text)
        return body['data']

def is_valid_job_application(profile):
    # modify criteria as needed
    return is_job_applicant(" ".join(profile.messages)) and profile.complete == True and (profile.is_engineer or profile.is_designer)

def get_complete_job_applications(access):
    # filter user_table for engineering applicants with complete submissions
    valid_applicants = { key:value for (key, value) in user_table.items() if is_valid_job_application(value)}
    if (len(valid_applicants)>0):
        engineers = []
        designers = []
        twitter_profiles = get_user_profiles(access, valid_applicants)
        for profile in twitter_profiles:
            user = user_table[profile[KEY_ID]]
            user.set_user_info(profile)
            user_table[profile[KEY_ID]] = user
            if (user.is_engineer):
                engineers.append(user)
            if (user.is_designer):
                designers.append(user)

        return engineers, designers
    return [], []
    
def query_dms(access, page = -1):

    response = get_user_conversation_events(access, page)

    body = json.loads(response.text)

    # parse each message
    for dm in body['data']:
        dm_date = dateutil.parser.parse(dm[KEY_TIMESTAMP])
        if (dm_date < cutoff_date):
            print("End of possible job applications reached")
            # TODO use last timestamp to reduce number of queries on subsequent runs
            config.set('DATES', 'LAST_DM_PARSED', dm[KEY_TIMESTAMP])
            profiles = get_complete_job_applications(access)
            if len(profiles[0])==0 and len(profiles[1])==0:
                print("No applicants found")
            else:
                spreadsheet.update_sheets(profiles[0], profiles[1])
            return True
        else:
            update_user_profile(access, dm)

    return query_dms(access, body[KEY_META][KEY_NEXT_PAGE])

def main():
    access = handle_oauth()
    query_dms(access)
    
if __name__ == "__main__":
    main()
