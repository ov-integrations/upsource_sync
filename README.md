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
  + RE Issue trackor type
  + REA Issue Task trackor type

To start integration, you need to fill file settings.json, example:
```
{
    "urlOneVizion": "trackor.onevizion.com",
    "loginOneVizion": "login",
    "passOneVizion": "********",
    "productOneVizion": "OneVizion",
    "issueTrackorType": "Issue",
    "issueTaskTrackorType": "Issue_Task",

    "urlUpsource": "upsource.onevizion.com",
    "userNameUpsource": "Trackor Integration",
    "loginUpsource": "login",
    "passUpsource": "********",
    "projectUpsource": "ov",
    "reviewScopes": [
        {
            "label": "Java",
            "filePatterns": [
                "java"
            ],
            "reviewers": [
                {
                    "name": "Full Name1",
                    "ovName" : "ov.name",
                    "token": "token1"
                }
            ]
        },
        {
            "label": "Js",
            "filePatterns": [
                "js",
                "css"
            ],
            "reviewers": [
                {
                    "name": "Full Name2",
                    "ovName" : "ov.name",
                    "token": "token2"
                }
            ]
        }
    ],
    "issueStatuses": {
        "test": "Test",
        "readyForMerge": "Ready for Merge",
        "closed": "Closed",
        "completed": "Completed",
        "canceled": "Canceled",
        "inProgress": "In Progress",
        "readyForReview": "Ready for Review"
    },
    "issueFields": {
        "id": "TRACKOR_ID",
        "title": "TRACKOR_KEY",
        "status": "VQS_IT_STATUS",
        "summary": "VQS_IT_XITOR_NAME",
        "product": "Product.TRACKOR_KEY",
        "codeReviewUrl": "I_CODE_REVIEW",
        "uatReleaseDate": "Version.VER_UAT_DATE"
    },
    "issueTaskFields": {
        "id": "TRACKOR_ID",
        "status": "IT_STATUS",
        "summary": "IT_DESCRIPTION",
        "type": "IT_TASK_TYPE",
        "estHours": "IT_EST_HOURS",
        "assignedTo": "IT_ASSIGNED_TO",
        "issue": "Issue.TRACKOR_KEY",
        "reviewer": "IT_CODE_REVIEWER",
        "codeReviewUrl": "IT_CODE_REVIEW_URL"
    },
    "issueTaskTypes": {
        "codeReview": "CR",
        "codeReviewLabel": "Code Review"
    },
    "issueTaskStatuses": {
        "opened": "Opened",
        "awaitingResponse": "Awaiting Response",
        "completed": "Completed"
    }
}
```
