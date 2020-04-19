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
            "reviewers": [
                "Full Name2"
            ]
        }
    ]
}
```
