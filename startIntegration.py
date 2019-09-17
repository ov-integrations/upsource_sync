import upsourceIntegration
import json

with open('SettingsFile.integration', "rb") as PFile:
    password_data = json.loads(PFile.read().decode('utf-8'))

url_upsource = password_data["urlUpsource"]
login_upsource = password_data["loginUpsource"]
pass_upsource = password_data["passUpsource"]
project_upsource = password_data["projectUpsource"]

url_onevizion = password_data["urlOneVizion"]
login_onevizion = password_data["loginOneVizion"]
pass_onevizion = password_data["passOneVizion"]
project_onevizion = password_data["projectOneVizion"]
trackor_type = password_data["trackorType"]

upsourceIntegration.Integration(url_upsource=url_upsource, login_upsource=login_upsource, pass_upsource=pass_upsource, project_upsource=project_upsource, url_onevizion=url_onevizion, login_onevizion=login_onevizion, pass_onevizion=pass_onevizion, project_onevizion=project_onevizion, trackor_type=trackor_type)
