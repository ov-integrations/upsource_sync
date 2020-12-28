# upsource_sync
![](./icon.png)

Integrates [JetBrains Upsource](https://www.jetbrains.com/upsource/) code review tool with OneVizion Issue Trackor

Requirements
- python version 3.7.2 or later
- python requests library (pip install requests)
- python onevizion library (pip install onevizion)

Features
- supports multiple products
- creates new code reviews for "Code Review" Issues
- assigns reviewer based on Issue Task
- adds statuses Accepted\Raise Concern to reviewer based on Issue Task

Permissions for user Trackor Integration:
- upsource
  + Close Upsource Code Review
  + Edit Upsource Content
  + Edit Upsource Project
  + View Upsource Content
  + View Upsource Project

- onevizion
  + WEB_SERVICES R
  + MODIFY_READONLY_DATA RE
  
  + \<Issue Trackor Type\> RE 
  + \<Issue Task Trackor Type\> REA
  + \<Product Trackor Type\> R
  + \<Version Trackor Type\> R

  + \<Issue Trackor Type Tab\> RE 
  + \<Issue Task Trackor Type Tab\> RE
  + \<Product Trackor Type Tab\> R
  + \<Version Trackor Type Tab\> R
  
  + \<Issue --> Issue Task Relation\> RA
  + \<Product --> Version Relation\> R
  + \<Version --> Issue Relation\> R
