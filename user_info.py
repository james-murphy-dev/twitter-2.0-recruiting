import re
from urlextract import URLExtract
from urllib.parse import urlsplit
import requests
import configparser

from user_info_constants import *
from keywords import *
from api_resp_attrs.twitter import *

config = configparser.ConfigParser()
config.read("config.ini")

HOSTNAME_LINKEDIN = config['KNOWN_HOSTS']['LINKEDIN']
HOSTNAME_GITHUB = config['KNOWN_HOSTS']['GITHUB']

minimum_link_count = 1 # complete submissions need at least 1 non-LinkedIn link

# job applicant class
class Profile(object):
    def __init__(self, user) -> None:
        self.username = user.username
        self.displayname = user.name
        self.avatar = user.profile_image_url
        self.is_engineer = False
        self.designer = False
        self.emails = []
        self.linkedin = None
        self.github = []
        self.other_links = []
        self.messages = []
        self.first_dm_time = None
        self.last_dm_time = None
        self.attachment = False
        self.keywords = { KEY_ALL : [] } # job-specific keywords also stored here
        self.experience = None
        self.complete = False

    def get_link_count(self):
        # decide if you want to allow LinkedIn alone to complete a submission
        return len(self.github) + len(self.other_links)
    
    def extract_dm_info(self, dm):
        if (self.last_dm_time is None):
            self.last_dm_time = dm[KEY_TIMESTAMP]

        # DMs are processed in reverse-chronolgical order, so no condion needed
        self.first_dm_time = dm[KEY_TIMESTAMP]

        # identify role(s) applying for
        if (is_engineering_applicant(dm[KEY_TEXT])):
            self.is_engineer = True
            # scan message for potential keywords
            self.extract_keywords_eng(dm)

        if (is_design_applicant(dm[KEY_TEXT])):
            self.designer = True
            self.extract_keywords_design(dm)

        # identify links, match with user profile stored in hash table
        links = self.parse_links(dm)

        # add text contents of DM (cover letter/resume) to user profile 
        # DMs are returned from API in reverse-chronological order, so prepend each one to the beginning of messages list
        # exclude DMs only containing links (redundant)
        # TODO add timestamps to each message
        if (not (len(links) == 1 and len(dm[KEY_TEXT]) == len(links[0]))):
            self.messages = [dm[KEY_TEXT]] + self.messages

        # check if applicant attached an image (resume, portfolio, etc.)
        if (self.attachment is False and dm[KEY_ATTACHMENT] is not None):
            self.attachment = True

        # scan message for years of experience
        # find 'years of experience' instances and insert highest number in user record
        exp_rx = get_exp_rx()
        exp_temp = exp_rx.search(dm[KEY_TEXT])
        if (exp_temp):
            try:
                if (len(exp_temp.groups()) > 0 and int(exp_temp.group(0)) > self.experience):
                    self.experience = int(exp_temp.group(0))
            except:
                print("Could not retrieve int value for years of experience")

        # check if user profile is complete
        if (self.get_link_count() >= minimum_link_count):
            self.complete = True

    def extract_keywords_eng(self, dm):
        # languages, libraries, databases, SDKs, architectures
        for language in languages:
            if (dm[KEY_TEXT].lower().find(language.lower()) != -1):
                self.keywords[KEY_LANGUAGES][language] = True
                self.keywords[KEY_ALL].append(language)

        for db in databases:
            if (dm[KEY_TEXT].lower().find(db.lower()) != -1):
                    self.keywords[KEY_DATABASES][db] = True
                    self.keywords[KEY_ALL].append(db)
    
    def extract_keywords_design(self, dm):
        for tool in design_tools:
            if (dm[KEY_TEXT].lower().find(tool.lower()) != -1):
                self.keywords[KEY_TOOLS][tool] = True
                self.keywords[KEY_ALL].append(tool)
    
    def parse_links(self, dm):
        extractor = URLExtract(extract_email=True)
        links = extractor.find_urls(dm[KEY_TEXT], only_unique=True, with_schema_only=True)
        for link in links:
            # interpret full url
            r = requests.head(link, allow_redirects=True)
            split_url = urlsplit(r.url) # 'http://127.0.0.1/asdf/login.php?q=abc#stackoverflow'
        
            if (self.linkedin is None and split_url.hostname==HOSTNAME_LINKEDIN):
                # LinkedIn
                self.linkedin = split_url.path
            elif (split_url.hostname==HOSTNAME_GITHUB):
                # could be multiple GitHub links
                self.github.append(split_url.path)
            elif (is_email(r.url)):
                # could be multiple email addresses
                self.emails.append(r.url)
            else:
                self.other_links.append(r.url)

        return links

'''
DM parsing functions
'''

def is_engineering_applicant(message):
    return KEYWORD_ENG in message.lower() or KEYWORD_DEV in message.lower()

def is_design_applicant(message):
    # could potentially remove 'er' to catch more applicants
    return KEYWORD_DESIGNER in message.lower()

def is_email(link):
    return re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", link)

def get_exp_rx():
    return re.compile(r"(\d+(?:-\d+)?\+?)\s*(years of experience?)", re.I)