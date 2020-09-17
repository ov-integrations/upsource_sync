# upsource_sync
![](./icon.png)

Integrates [JetBrains Upsource](https://www.jetbrains.com/upsource/) code review tool with OneVizion Issue Trackor

Requirements
- python version 3.7.2 or later
- python requests library (pip install requests)
- python onevizion library (pip install onevizion)

Features
- creates new code reviews for "Ready for Review" Issues
- creates new Code Review Issue Tasks
- updates statuses of Code Review Issue Tasks
- adds new commits to the reviews (restores statuses if there are no changes related to the review scope)
- assigns reviewer based on the file type
- assigns a default reviewer from the default review scope if no one is assigned to the review
- adds and removes review labels:
  + when creating a review, XXX label depending on the type of code will be added 
  + when concern raised, !XXX label related to this reviewer will be added, XXX label will be removed
  + label "work in progress" is added when the Issue status changed back to "In Process"
  + label "current release" is added, when related Issue targeted for the next release and will be removed, when current release is tested in UAT and released in PROD

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
