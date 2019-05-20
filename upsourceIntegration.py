import requests
from requests.auth import HTTPBasicAuth
import json
import logging
import sys

class integration(object):

    def __init__(self, urlUpsource="", loginUpsource="", passUpsource="", urlOnevizion="", loginOnevizion="", passOnevizion="", projectName="", projectOnevizion=""):
        self.urlUpsource = urlUpsource
        self.loginUpsource = loginUpsource
        self.passUpsource = passUpsource
        self.urlOnevizion = urlOnevizion
        self.loginOnevizion = loginOnevizion
        self.passOnevizion = passOnevizion
        self.projectName = projectName
        self.projectOnevizion = projectOnevizion
        
        authUpsource = HTTPBasicAuth(loginUpsource, passUpsource)
        authOnevizion = HTTPBasicAuth(loginOnevizion, passOnevizion)
        headers = {'Content-type':'application/json','Content-Encoding':'utf-8'}
        self.reviewInfo(urlOnevizion, authOnevizion, urlUpsource, authUpsource, projectName, projectOnevizion, headers)
        self.createReview(urlOnevizion, authOnevizion, urlUpsource, authUpsource, projectName, projectOnevizion, headers)
        
    #Returns short review information for a set of revisions
    def reviewInfo(self, urlOnevizion, authOnevizion, urlUpsource, authUpsource, projectName, projectOnevizion, headers):
        log = self.get_logger()
        log.debug('Upsource integration started')
        log.debug('Issues statuses updation started')
        for revisionId in self.revisionList(urlUpsource, authUpsource, projectName, headers):
            url = urlUpsource + '~rpc/getRevisionReviewInfo'
            data = {"projectId":projectName, "revisionId":revisionId['revisionId']}
            answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
            response = answer.json()
            readble_json = response['result']['reviewInfo']
            if readble_json == [{}]:
                log.debug('This revision has no review')
            else:
                for issues in readble_json:
                    for iss in issues:
                        iss = issues
                        issueTitle = iss['reviewInfo']['title']
                        self.checkStatus(urlOnevizion, authOnevizion, projectOnevizion, headers, self.getIssueTitle(issueTitle), iss['reviewInfo']['state'], self.revisionBranche(urlUpsource, authUpsource, projectName, headers, revisionId['revisionId']))
        log.debug('Issues statuses updation finished')

    #Returns the list of revisions in a given project
    def revisionList(self, urlUpsource, authUpsource, projectName, headers):
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
    
    #Returns the list of branches a revision is part of
    def revisionBranche(self, urlUpsource, authUpsource, projectName, headers, revisionId):
        url = urlUpsource + '~rpc/getRevisionBranches'
        data = {"projectId":projectName, "revisionId":revisionId}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
        response = answer.json()
        readble_json = response['result']['branchName']
        return readble_json
    
    #Checks review status and run updateIssue
    def checkStatus(self, urlOnevizion, authOnevizion, projectOnevizion, headers, issue, status, branch):
        log = self.get_logger()
        if issue == 'None':
            return None
        else:
            if status == '2' and branch == 'master':
                self.updateIssue(self, urlOnevizion, authOnevizion, projectOnevizion, headers, issue, 'Ready for Merge')
            elif status == '2' and branch != 'master':
                self.updateIssue(self, urlOnevizion, authOnevizion, projectOnevizion, headers, issue, 'Ready for Test')
            else: log.debug('Review ' + str(issue) + ' is not yet closed')

    #Updates issue status if review status = 2 (closed)
    def updateIssue(self, urlOnevizion, authOnevizion, projectOnevizion, headers, issue, status):
        log = self.get_logger()
        for issueTitle in self.checkIssue(self, urlOnevizion, authOnevizion, projectOnevizion, headers, issue):
            if issueTitle['VQS_IT_STATUS'] == 'Ready for Review' and status == 'Ready for Merge':
                data = {"VQS_IT_STATUS":status}
                url = urlOnevizion + 'api/v3/trackors/' + issueTitle['XITOR_ID']
                answer = requests.post(url, headers=headers, data=data, auth=authOnevizion)
                log.debug('Issue ' + issueTitle['XITOR_ID'] + ' updated status to "Ready for Merge"')
            elif issueTitle['VQS_IT_STATUS'] == 'Ready for Review' and status == 'Ready for Test':
                data = {"VQS_IT_STATUS":status}
                url = urlOnevizion + 'api/v3/trackors/' + issueTitle['XITOR_ID']
                answer = requests.post(url, headers=headers, data=data, auth=authOnevizion)
                log.debug('Issue ' + issueTitle['XITOR_ID'] + ' updated status to "Ready for Test"')
            else: log.debug('Issue ' + issueTitle['XITOR_ID'] + ' has already been updated')

    #Checks issue status
    def checkIssue(self, urlOnevizion, authOnevizion, projectOnevizion, headers, issue):
        if issue == '':
            url = urlOnevizion + 'api/v3/trackor_types/Issue/trackors'
            params = {"fields":"XITOR_KEY, VQS_IT_STATUS, Product.TRACKOR_KEY", "VQS_IT_STATUS":"Ready for Review", "Product.TRACKOR_KEY":projectOnevizion}
            answer = requests.get(url, headers=headers, params=params, auth=authOnevizion)
            return answer
        else:
            url = urlOnevizion + 'api/v3/trackor_types/Issue/trackors'
            params = {"fields":"XITOR_KEY, VQS_IT_STATUS, Product.TRACKOR_KEY", "XITOR_KEY":issue, "Product.TRACKOR_KEY":projectOnevizion}
            answer = requests.get(url, headers=headers, params=params, auth=authOnevizion)
            return answer

    #Creates review if issue status = 'Ready for Review'
    def createReview(self, urlOnevizion, authOnevizion, urlUpsource, authUpsource, projectName, projectOnevizion, headers):
        log = self.get_logger()
        log.debug('Reviews creation started')
        for issue in self.checkIssue(urlOnevizion, authOnevizion, projectOnevizion, headers, ''):
            try:
                issue == issue['XITOR_KEY']
            except Exception:
                log.debug('Not need to create a review for this issue - ' + str(issue))
            else:
                for revisionId in self.filteredRevisionList(authUpsource, urlUpsource, projectName, headers, issue):
                    url = urlUpsource + '~rpc/getRevisionReviewInfo'
                    data = {"projectId":projectName, "revisionId":revisionId['revisionId']}
                    answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
                    response = answer.json()
                    readble_json = response['result']['reviewInfo']
                    if readble_json is not None:
                        log.debug('Review already exists')
                    else:
                        url = urlUpsource + '~rpc/createReview'
                        data = {"projectId":projectName, "revisions":revisionId['revisionId']}
                        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
                        log.debug('Review for ' + issue + ' created')
        log.debug('Reviews creation finished')
        log.debug('Upsource integration finished')

    #Returns the list of revisions that match the given search query
    def filteredRevisionList(self, authUpsource, urlUpsource, projectName, headers, issue):
        url = urlUpsource + '~rpc/getRevisionsListFiltered'
        data = {"projectId":projectName, "limit":1, "query":issue}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
        response = answer.json()
        readble_json = response['result']['revision']
        return readble_json

    #Returns logging to stdout
    def get_logger(self, name=__file__, file='log.txt', encoding='utf-8'):
        log = logging.getLogger(name)
        log.setLevel(logging.DEBUG)
        formatter = logging.Formatter('[%(asctime)s] %(filename)s:%(lineno)d %(levelname)-8s %(message)s')
        sh = logging.StreamHandler(stream=sys.stdout)
        sh.setFormatter(formatter)
        log.addHandler(sh)
        return log
