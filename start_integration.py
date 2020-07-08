from upsource_integration import Integration, Issue, Review
from integration_log import build_logger
from jsonschema import validate
import json
import re

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
project_upsource = password_data["projectUpsource"]
review_scopes = password_data["reviewScopes"]

url_onevizion = re.sub("^https://", "", password_data["urlOneVizion"][:-1])
login_onevizion = password_data["loginOneVizion"]
pass_onevizion = password_data["passOneVizion"]
product_onevizion = password_data["productOneVizion"]
trackor_type = password_data["trackorType"]

logger = build_logger()
issue = Issue(url_onevizion, login_onevizion, pass_onevizion, product_onevizion, trackor_type)
review = Review(url_upsource, user_name_upsource, login_upsource, pass_upsource, project_upsource, review_scopes, logger)
integration = Integration(issue, review, logger)

integration.start_integration()
