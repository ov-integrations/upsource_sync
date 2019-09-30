# upsource_sync
![](./icon.png)

Integrates [JetBrains Upsource](https://www.jetbrains.com/upsource/) code review tool with OneVizion Issue Trackor

Requirements
- python version 3.7.2
- python requests library (pip install requests)
- python onevizion library (pip install onevizion)

Features
- creates new code reviews based for "Ready for Review" issues
- updates issue status when code review is closed
- supports git feature branches (branch tracking reviews are created)
- adds new commits to the reviews in master branch

To start integration, you need to fill files

settings_template.json:

For Upsource:
- URL to site (e.g., upsource.onevizion.com)
- account username and password 
- project (e.g., ov)

For OneVizion:
- URL to site (e.g., trackor.onevizion.com)
- account username and password 
- product (e.g., OneVizion)
- trackor type (e.g., Issue)

.integration:
- settings_file_name (File that contains additional settings. e.g., settings_template.json)
- default_schedule (Must be specified in the quartz cron expression format. e.g., 0 * * * * ?)
- read_from_stdout (Checkbox that indicates that STDOUT is added to Log Trackor. e.g., true)

After that run startIntegration.py
