from Integration import Integration
from Issue import Issue
from Review import Review

import json

with open('settings.json', "rb") as PFile:
    password_data = json.loads(PFile.read().decode('utf-8'))

url_upsource = password_data["urlUpsource"]
user_name_upsource = password_data["userNameUpsource"]
login_upsource = password_data["loginUpsource"]
pass_upsource = password_data["passUpsource"]
project_upsource = password_data["projectUpsource"]
review_scopes = password_data["reviewScopes"]

url_onevizion = password_data["urlOneVizion"]
login_onevizion = password_data["loginOneVizion"]
pass_onevizion = password_data["passOneVizion"]
product_onevizion = password_data["productOneVizion"]
trackor_type = password_data["trackorType"]

issue = Issue(url_onevizion, login_onevizion, pass_onevizion, product_onevizion, trackor_type)
review = Review(url_upsource, user_name_upsource, login_upsource, pass_upsource, project_upsource, review_scopes)
integration = Integration(issue, review)

integration.start_integration()
