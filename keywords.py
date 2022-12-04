# recognized keywords
KEYWORD_ENG = 'engineer'
KEYWORD_DEV = 'developer'
KEYWORD_PROG = 'programmer'
KEYWORD_DESIGNER = 'designer'

job_application_keywords = [KEYWORD_ENG, KEYWORD_DEV, KEYWORD_PROG, KEYWORD_DESIGNER]
languages = ["C", "C++", "C#", "Golang", "Java", "JavaScript", "HTML", "CSS", "Kotlin", "Swift", "Python", "Ruby", "PHP", "Scala", "Rust", "React", "Angular", "node.js"]
databases = ["SQL", "NoSQL", "PostgreSQL" "MongoDB"]
design_tools = ["Figma", "Moqups", "Illustrator", "Photoshop", "Webflow", "InVision", "Balsamiq"]

def is_job_applicant(dm):
    return any(ext in dm for ext in job_application_keywords)
