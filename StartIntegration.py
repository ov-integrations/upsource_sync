from UpsourceIntegration import Integration
import json

with open('settings.json', "rb") as PFile:
    password_data = json.loads(PFile.read().decode('utf-8'))

url_upsource = password_data["urlUpsource"]
login_upsource = password_data["loginUpsource"]
pass_upsource = password_data["passUpsource"]
project_upsource = password_data["projectUpsource"]
departments = password_data["departments"]

url_onevizion = password_data["urlOneVizion"]
login_onevizion = password_data["loginOneVizion"]
pass_onevizion = password_data["passOneVizion"]
product_onevizion = password_data["productOneVizion"]
trackor_type = password_data["trackorType"]

upsource_integration = Integration(url_upsource=url_upsource, login_upsource=login_upsource, pass_upsource=pass_upsource,
                                project_upsource=project_upsource, departments=departments, url_onevizion=url_onevizion,
                                login_onevizion=login_onevizion, pass_onevizion=pass_onevizion, product_onevizion=product_onevizion,
                                trackor_type=trackor_type)
upsource_integration.start_integration()