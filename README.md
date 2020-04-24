# upsource_sync
![](./icon.png)

Integrates [JetBrains Upsource](https://www.jetbrains.com/upsource/) code review tool with OneVizion Issue Trackor

Requirements
- python version 3.7.2 or later
- python requests library (pip install requests)
- python onevizion library (pip install onevizion)

Features
- creates new code reviews based for "Ready for Review" issues
- updates issue status when code review is closed
- supports git feature branches (branch tracking reviews are created)
- adds new commits to the reviews in master branch
- assigns reviewer based on the file type
- adds and removes review labels:
  + when creating a review, XXX label depending on the type of code will be added 
  + when concern raised, !XXX label related to this reviewer will be added, XXX label will be removed
  + label "work in progress" is added when the Issue status changed back to "In Process"
  + label "current release" is added when started UAT release and lasts 2 weeks, after which it is deleted

To start integration, you need to fill file settings.json, example:
```
{
    "urlOneVizion": "trackor.onevizion.com",
    "loginOneVizion": "login",
    "passOneVizion": "********",
    "productOneVizion": "OneVizion",
    "trackorType": "Issue",

    "urlUpsource": "upsource.onevizion.com",
    "loginUpsource": "login",
    "passUpsource": "********",
    "projectUpsource": "ov",
    "departments": [
        {
            "name": "backend",
            "filePatterns": [
                "java"
            ],
            "reviewLabel" : "label name1",
            "reviewers": [
                "Full Name1"
            ]
        },
        {
            "name": "frontend",
            "filePatterns": [
                "js",
                "css"
            ],
            "reviewLabel" : "label name2",
            "reviewers": [
                "Full Name2"
            ]
        }
    ]
}
```
