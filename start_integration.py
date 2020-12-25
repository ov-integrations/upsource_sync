from jsonschema import validate

from integration_log import build_logger
from upsource_integration import *

with open('settings.json', "rb") as PFile:
    password_data = json.loads(PFile.read().decode('utf-8'))

with open('settings_schema.json', "rb") as PFile:
    data_schema = json.loads(PFile.read().decode('utf-8'))

try:
    validate(instance=password_data, schema=data_schema)
except Exception as e:
    raise Exception("Incorrect value in the settings file\n{}".format(str(e)))

url_upsource = password_data["urlUpsource"]
user_name_upsource = password_data["userNameUpsource"]
login_upsource = password_data["loginUpsource"]
pass_upsource = password_data["passUpsource"]
products = password_data["products"]
reviewers = password_data["reviewers"]

url_onevizion = re.sub("^https://", "", password_data["urlOneVizion"][:-1])
login_onevizion = password_data["loginOneVizion"]
pass_onevizion = password_data["passOneVizion"]
issue_trackor_type = password_data["issueTrackorType"]
issue_task_trackor_type = password_data["issueTaskTrackorType"]

issue_statuses = password_data["issueStatuses"]
issue_fields = password_data["issueFields"]
issue_task_fields = password_data["issueTaskFields"]
issue_task_types = password_data["issueTaskTypes"]
issue_task_statuses = password_data["issueTaskStatuses"]

logger = build_logger()
issue = Issue(url_onevizion, login_onevizion, pass_onevizion,
              issue_trackor_type, issue_statuses, issue_fields)
issue_task = IssueTask(url_onevizion, login_onevizion, pass_onevizion, issue_trackor_type, issue_task_trackor_type,
                       issue_fields, issue_task_fields, issue_task_types, issue_task_statuses)
review = Review(url_upsource, user_name_upsource,
                login_upsource, pass_upsource, reviewers, logger)
integration = Integration(products, issue, issue_task, review, logger)

integration.start_integration()
