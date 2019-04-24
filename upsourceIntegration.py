import requests
from requests.auth import HTTPBasicAuth
import json

class integration(object):

    def __init__(self, urlUpsource="", loginUpsource="", passUpsource="", urlOnevizion="", loginOnevizion="", passOnevizion="", projectName=""):
        self.urlUpsource = urlUpsource
        self.loginUpsource = loginUpsource
        self.passUpsource = passUpsource
        self.urlOnevizion = urlOnevizion
        self.loginOnevizion = loginOnevizion
        self.passOnevizion = passOnevizion
        self.projectName = projectName

        authUpsource = HTTPBasicAuth(loginUpsource, passUpsource)
        authOnevizion = HTTPBasicAuth(loginOnevizion, passOnevizion)
        headers = {'Content-type':'application/json','Content-Encoding':'utf-8'}
        self.reviewInfo(authUpsource, urlUpsource, projectName, authOnevizion, urlOnevizion, headers)
        
    #Returns short review information for a set of revisions
    def reviewInfo(self, authUpsource, urlUpsource, projectName, authOnevizion, urlOnevizion, headers):
        for revisionId in self.revisionList(authUpsource, urlUpsource, projectName, headers):
            url = urlUpsource + '~rpc/getRevisionReviewInfo'
            data = {"projectId":projectName, "revisionId":revisionId['revisionId']}
            answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
            response = answer.json()
            readble_json = response['result']['reviewInfo']
            if readble_json == [{}]:
                for issueTitle in self.checkIssue(urlOnevizion, authOnevizion, headers, 'IS1041'):
                    if issueTitle['VQS_IT_STATUS'] == 'Ready for Review':
                        self.createReview(urlUpsource, authUpsource, projectName, headers, revisionId['revisionId'])
            elif readble_json is not None:
                    for issues in readble_json:
                        for iss in issues:
                            iss = issues
                            issueTitle = iss['reviewInfo']['title']
                            self.checkStatus(urlOnevizion, authOnevizion, headers, self.getIssueTitle(issueTitle), iss['reviewInfo']['state'], self.revisionBranche(urlUpsource, authUpsource, projectName, headers, revisionId['revisionId']))

    #Returns the list of revisions in a given project
    def revisionList(self, authUpsource, urlUpsource, projectName, headers):
        url = urlUpsource + '~rpc/getRevisionsList'
        data = {"projectId":projectName, "limit":1000}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
        response = answer.json()
        readble_json = response['result']['revision']
        return readble_json

    #Returns issue title
    def getIssueTitle(self, issueTitle):
        if 'Revert \"' in issueTitle:
            return None
        elif 'Review of ' in issueTitle:
            return None
        elif 'Merge branch \"' in issueTitle:
            return None
        elif 'Merge branch \'master\' into ' in issueTitle:
            return None
        else:
            return issueTitle[issueTitle.find('') : issueTitle.find(' ')]

    #Checks issue status
    def checkIssue(self, urlOnevizion, authOnevizion, headers, issue):
        url = urlOnevizion + 'api/v3/trackor_types/Issue/trackors'
        params = {"fields":"VQS_IT_STATUS, XITOR_KEY", "XITOR_KEY":issue}
        answer = requests.get(url, headers=headers, params=params, auth=authOnevizion)
        response = answer.json()
        return response

    #Creates review if issue status = 'Ready for Review'
    def createReview(self, urlUpsource, authUpsource, projectName, headers, revisionId):
        url = urlUpsource + '~rpc/createReview'
        data = {"projectId":projectName, "revisions":revisionId}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)

    #Returns the list of branches a revision is part of
    def revisionBranche(self, urlUpsource, authUpsource, projectName, headers, revisionId):
        url = urlUpsource + '~rpc/getRevisionBranches'
        data = {"projectId":projectName, "revisionId":revisionId}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
        response = answer.json()
        readble_json = response['result']['branchName']
        return readble_json

    #Checks review status and run updateIssue
    def checkStatus(self, urlOnevizion, authOnevizion, headers, issue, status, branch):
        if issue == 'None':
            return None
        else:
            if status == '2' and branch == 'master':
                self.updateIssue(self, urlOnevizion, authOnevizion, headers, issue, 'Ready for Merge')
            elif status == '2' and branch != 'master':
                self.updateIssue(self, urlOnevizion, authOnevizion, headers, issue, 'Ready for Test')

    #Updates issue status if review status = 2 (closed)
    def updateIssue(self, urlOnevizion, authOnevizion, headers, issue, status):
        for issueTitle in self.checkIssue(self, urlOnevizion, authOnevizion, headers, issue):
            if issueTitle['VQS_IT_STATUS'] == 'Ready for Review' and status == 'Ready for Merge':
                data = {"VQS_IT_STATUS":status}
                url = urlOnevizion + 'api/v3/trackors/' + issueTitle['XITOR_ID']
                answer = requests.post(url, headers=headers, data=data, auth=authOnevizion)
            elif issueTitle['VQS_IT_STATUS'] == 'Ready for Review' and status == 'Ready for Test':
                data = {"VQS_IT_STATUS":status}
                url = urlOnevizion + 'api/v3/trackors/' + issueTitle['XITOR_ID']
                answer = requests.post(url, headers=headers, data=data, auth=authOnevizion)
