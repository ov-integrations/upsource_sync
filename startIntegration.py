import upsourceIntegration
import json

with open('SettingsFile.integration', "rb") as PFile:
    password_data = json.loads(PFile.read().decode('utf-8'))

url_upsource = password_data["urlUpsource"]
login_upsource = password_data["loginUpsource"]
pass_upsource = password_data["passUpsource"]

url_onevizion = password_data["urlOnevizion"]
login_onevizion = password_data["loginOnevizion"]
pass_onevizion = password_data["passOnevizion"]
project_name = password_data["projectName"]
project_onevizion = password_data["projectOnevizion"]

upsourceIntegration.Integration(url_upsource=url_upsource, login_upsource=login_upsource, pass_upsource=pass_upsource, url_onevizion=url_onevizion, login_onevizion=login_onevizion, pass_onevizion=pass_onevizion, project_name=project_name, project_onevizion=project_onevizion)
