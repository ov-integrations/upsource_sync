# upsource_sync
Synchronize Issues in trackor.onevizion and Reviews in upsource.onevizion

In order for the integration to work it is necessary:
1) Install python version 3.7.2.
2) Install the request library. It is needed for URL requests to work.
The request library can be installed using pip: pip install requests.

After everything is set, you need to fill in the data for the SettingsFileTemplate.integration file:
1) URL to onevizion website
2) Username and password of the account on this site
3) URL to Upsource website
4) Username and password of the account on this site
5) Name of the project that needs integration
