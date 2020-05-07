# upsource_sync
![](./icon.png)

Integrates [JetBrains Upsource](https://www.jetbrains.com/upsource/) code review tool with OneVizion Issue Trackor

Requirements
- python version 3.7.2 or later
- python requests library (pip install requests)
- python onevizion library (pip install onevizion)

Features
- creates new code reviews for "Ready for Review" Issues
- updates Issue status when code review is closed
- supports git feature branches (branch tracking reviews are created)
- adds new commits to the reviews in master branch
- assigns reviewer based on the file type
- adds and removes review labels:
  + when creating a review, XXX label depending on the type of code will be added 
  + when concern raised, !XXX label related to this reviewer will be added, XXX label will be removed
  + label "work in progress" is added when the Issue status changed back to "In Process"
  + label "current release" is added, when related Issue targeted for the next release and will be removed, when current release is tested in UAT and released in PROD

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
    "reviewScopes": [
        {
            "label" : "label name1",
            "filePatterns": [
                "java"
            ],
            "reviewers": [
                "Full Name1"
            ]
        },
        {
            "label" : "label name2",
            "filePatterns": [
                "js",
                "css"
            ],
            "reviewers": [
                "Full Name2"
            ]
        }
    ]
}
```
