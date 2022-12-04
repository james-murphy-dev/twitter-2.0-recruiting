from user_info_constants import *
from keywords import *
import configparser
import gspread
import dateutil.parser

config = configparser.ConfigParser()
config.read("config.ini")

HOSTNAME_LINKEDIN = config['KNOWN_HOSTS']['LINKEDIN']
HOSTNAME_GITHUB = config['KNOWN_HOSTS']['GITHUB']

class Workbook():
    TITLE = "Twitter 2.0 recruiting"
    ENG_SHEET = "Engineering"
    DESIGN_SHEET = "Design"
    COL_USERNAME = "Username"
    COL_EMAILS =  "Email(s)"
    COL_LINKEDIN = "LinkedIn"
    COL_GITHUB = "GitHub links"
    COL_OTHER_LINKS = "Other links"
    COL_MESSAGES = "DM contents"
    COL_ATTACHMENTS = "Attachment(s)"
    COL_LAST_DM = "Most recent DM"
    COL_STATUS = "Status"
    # Engineering
    COL_LANGUAGES = "Languages"
    COL_DB = "Databases"
    # Design
    COL_DESIGN_TOOLS = "Tools"

    SHEET_COLUMNS = [
        COL_USERNAME, COL_EMAILS, COL_LINKEDIN, COL_GITHUB, COL_OTHER_LINKS, COL_MESSAGES, COL_ATTACHMENTS, COL_LAST_DM, COL_STATUS    
    ]

    ENG_SHEET_COLUMNS = SHEET_COLUMNS + [COL_LANGUAGES, COL_DB] + languages + databases
    DESIGN_SHEET_COLUMNS = SHEET_COLUMNS + [COL_DESIGN_TOOLS] + design_tools

    def get_last_column(self, sheet):
        match sheet:
            case self.ENG_SHEET:
                get_eng_sheet_last_column()
            case self.DESIGN_SHEET:
                get_design_sheet_last_column()

def get_linkedin_cell(path):
    if (path==None):
        return None
    return f"=HYPERLINK(\"{HOSTNAME_LINKEDIN+path}\", \"{path}\")"

def get_github_cell(path):
    return f"=HYPERLINK({HOSTNAME_GITHUB+path}, {path})"

def recursive_items(dictionary):
    for key, value in dictionary.items():
        if type(value) is dict:
            yield from recursive_items(value)
        else:
            yield (key, value)

def get_keyword_columns_eng(keywords):
    keyword_cells = []
    for language in languages:
        if language in keywords:
            keyword_cells.append("Yes")
        else:
            keyword_cells.append("")
    for db in databases:
        if db in keywords:
            keyword_cells.append("Yes")
        else:
            keyword_cells.append("")
    return keyword_cells

def get_keyword_columns_design(keywords):
    keyword_cells = []
    for tool in design_tools:
        if tool in keywords:
            keyword_cells.append("Yes")
        else:
            keyword_cells.append("")
    return keyword_cells

def get_row_values(profile, sheet_title):
    row = [
        profile.username,
        profile.last_dm_time,
        "\n".join(profile.emails),
        get_linkedin_cell(profile.linkedin),
        "\n".join(profile.github),
        "\n".join(profile.other_links),
        "\n\n".join(profile.messages),
        profile.attachment,
        "\n".join(profile.keywords[KEY_ALL])
        # TODO include drop-down menu (Accept/Reject/Short-list) in status column
        ]

    all_keywords = profile.keywords[KEY_ALL]
    match sheet_title:
        case Workbook.ENG_SHEET:
            row+=get_keyword_columns_eng(all_keywords)
        case Workbook.DESIGN_SHEET:
            row+=get_keyword_columns_design(all_keywords)
    
    return [row]

def get_cell_range(row, last_col_letter):
    return f"A{row}:{last_col_letter}{row}"

def update_row(row, applicant, sheet, last_col_letter):
    cell_range = get_cell_range(row, last_col_letter)
    values = get_row_values(applicant, sheet.title)
    sheet.update(cell_range, values)

def add_row(applicant, sheet, last_col_letter):
    first_empty_row = next_available_row(sheet) #search for first empty cell
    update_row(first_empty_row, applicant, sheet, last_col_letter)

def next_available_row(worksheet):
    str_list = list(filter(None, worksheet.col_values(1)))
    return str(len(str_list)+1)

def update_rows(sheet, profiles, last_col_letter):
    updated_rows = 0
    new_rows = 0

     # update rows with new data, create new rows for new submissions
    for profile in profiles.values():
        # for each profile, determine if there is an existing row and if there is new data
        applicant_username_cell = sheet.find(profile.username)

        if (applicant_username_cell is not None and 
        dateutil.parser.parse(sheet.acell(f"H{applicant_username_cell.row}").value) < dateutil.parser.parse(profile.last_dm_date)):
            # if yes, update the row with any new data
            update_row(applicant_username_cell.row, profile, sheet, last_col_letter)
            updated_rows +=1
        else:
            # if no, create the row
            add_row(profile, sheet, last_col_letter)
            new_rows += 1

    return new_rows, updated_rows

def get_eng_sheet_last_column():
    return chr(len(Workbook.ENG_SHEET_COLUMNS) + 64)

def get_design_sheet_last_column():
    return chr(len(Workbook.DESIGN_SHEET_COLUMNS) + 64)

def is_valid_job_application(profile):
    return is_job_applicant(" ".join(profile.messages)) and profile.complete == True

def update_sheet(user_table):

    # filter user_table for engineering applicants with complete submissions
    engineers = { key:value for (key, value) in user_table.items() if is_valid_job_application(value) and value.engineer == True}
    designers = { key:value for (key, value) in user_table.items() if is_valid_job_application(value) and value.designer == True}

    gc = gspread.oauth(flow=gspread.auth.console_flow)

    # if spreadsheet is already created, open the existing file
    # TODO prompt user for spreadsheet name
    try:
        workbook = gc.open(Workbook.TITLE)
        eng_sheet = workbook.worksheet(Workbook.ENG_SHEET)
        design_sheet = workbook.worksheet(Workbook.DESIGN_SHEET)
    except:
        # create worksheets if the document is new
        workbook = gc.create(Workbook.TITLE)
        eng_sheet = workbook.add_worksheet(Workbook.ENG_SHEET, len(engineers)+1, len(Workbook.ENG_SHEET_COLUMNS))
        design_sheet = workbook.add_worksheet(Workbook.DESIGN_SHEET, len(designers)+1, len(Workbook.DESIGN_SHEET_COLUMNS))

        eng_sheet.update(f"A1:{get_eng_sheet_last_column()}1", [Workbook.ENG_SHEET_COLUMNS])
        design_sheet.update(f"A1:{get_design_sheet_last_column()}1", [Workbook.DESIGN_SHEET_COLUMNS])

    if (len(engineers)>0):
        update_eng_sheet(eng_sheet, engineers)
    else:
        print("No updated engineering profiles\n")
        
    if (len(designers)>0):
        update_design_sheet(design_sheet, designers)
    else:
        print("No updated design profiles\n")

    print(f"View your spreadsheet here: https://docs.google.com/spreadsheets/d/{workbook.id}")

    return True

def update_eng_sheet(sheet, profiles):
    rows = update_rows(sheet, profiles, get_eng_sheet_last_column())
    print("Engineering:")
    print(f"{rows[0]} profiles added")
    print(f"{rows[1]} profiles updated\n")

def update_design_sheet(sheet, profiles):
    rows = update_rows(sheet, profiles, get_design_sheet_last_column())
    print("Design:")
    print(f"{rows[0]} profiles added")
    print(f"{rows[1]} profiles updated\n")