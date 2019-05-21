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

        self.revisionList(urlOnevizion, authOnevizion, urlUpsource, authUpsource, projectName, projectOnevizion, headers)
        self.createReview(urlOnevizion, authOnevizion, urlUpsource, authUpsource, projectName, projectOnevizion, headers)

    #Returns the list of revisions in a given project
    def revisionList(self, urlOnevizion, authOnevizion, urlUpsource, authUpsource, projectName, projectOnevizion, headers):
        log = self.get_logger()
        log.info('Started upsource integration')
        log.info('Started updating the status of issues')

        skipNumber = 0
        while skipNumber != None:
            url = urlUpsource + '~rpc/getRevisionsList'
            data = {"projectId":projectName, "limit":1, "skip":skipNumber}
            answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
            response = answer.json()
            readble_json = response['result']

            if 'revision' in readble_json:
                skipNumber = skipNumber + 1
                revisionId = readble_json['revision'][0]['revisionId']

                reviewInfo = self.reviewInfo(urlUpsource, authUpsource, projectName, revisionId, headers)

                if reviewInfo == [{}]:
                    log.info('This revision has no review')
                else:
                    reviewTitle = self.getIssueTitle(reviewInfo[0]['reviewInfo']['title'])
                    reviewStatus = reviewInfo[0]['reviewInfo']['state']
                    reviewBranche = self.revisionBranche(urlUpsource, authUpsource, projectName, headers, revisionId)

                    self.checkStatus(urlOnevizion, authOnevizion, projectOnevizion, headers, reviewTitle, reviewStatus, reviewBranche)
            else:
                skipNumber = None
        log.info('Finished updating the status of issues')

    #Returns short review information for a set of revisions
    def reviewInfo(self, urlUpsource, authUpsource, projectName, revisionId, headers):
        url = urlUpsource + '~rpc/getRevisionReviewInfo'
        data = {"projectId":projectName, "revisionId":revisionId}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
        response = answer.json()
        readble_json = response['result']['reviewInfo']
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
            if status == 2 and branch == 'master':
                self.updateIssue(urlOnevizion, authOnevizion, projectOnevizion, headers, issue, 'Ready for Merge')
            elif status == 2 and branch != 'master':
                self.updateIssue(urlOnevizion, authOnevizion, projectOnevizion, headers, issue, 'Ready for Test')
            else: log.info('Review ' + str(issue) + ' is not yet closed')

    #Updates issue status if review status = 2 (closed)
    def updateIssue(self, urlOnevizion, authOnevizion, projectOnevizion, headers, issue, status):
        log = self.get_logger()

        issueTitle = self.checkIssue(urlOnevizion, authOnevizion, projectOnevizion, headers, issue)
        if issueTitle['VQS_IT_STATUS'] == 'Ready for Review' and status == 'Ready for Merge':
            url = urlOnevizion + 'api/v3/trackors/' + str(issueTitle['TRACKOR_ID'])
            data = {"VQS_IT_STATUS":status}
            answer = requests.put(url, headers=headers, data=json.dumps(data), auth=authOnevizion)
            log.info('Issue ' + issueTitle['TRACKOR_KEY'] + ' updated status to "Ready for Merge"')
        elif issueTitle['VQS_IT_STATUS'] == 'Ready for Review' and status == "Ready for Test":
            url = urlOnevizion + 'api/v3/trackors/' + str(issueTitle['TRACKOR_ID'])
            data = {"VQS_IT_STATUS":status}
            answer = requests.put(url, headers=headers, data=json.dumps(data), auth=authOnevizion)
            log.info('Issue ' + issueTitle['TRACKOR_KEY'] + ' updated status to "Ready for Test"')
        else: log.info('Issue ' + issueTitle['TRACKOR_KEY'] + ' has already been updated')

    #Checks issue status
    def checkIssue(self, urlOnevizion, authOnevizion, projectOnevizion, headers, issue):
        if issue == '':
            url = urlOnevizion + 'api/v3/trackor_types/Issue/trackors'
            params = {"fields":"TRACKOR_KEY, VQS_IT_STATUS, Product.TRACKOR_KEY", "Product.TRACKOR_KEY":projectOnevizion}
            answer = requests.get(url, headers=headers, params=params, auth=authOnevizion)
            response = answer.json()
            return response
        else:
            url = urlOnevizion + 'api/v3/trackor_types/Issue/trackors'
            params = {"fields":"TRACKOR_KEY, VQS_IT_STATUS, Product.TRACKOR_KEY", "TRACKOR_KEY":issue, "Product.TRACKOR_KEY":projectOnevizion}
            answer = requests.get(url, headers=headers, params=params, auth=authOnevizion)
            response = answer.json()
            return response

    #Creates review if issue status = 'Ready for Review'
    def createReview(self, urlOnevizion, authOnevizion, urlUpsource, authUpsource, projectName, projectOnevizion, headers):
        log = self.get_logger()
        log.info('Started creating reviews')
        for issue in self.checkIssue(urlOnevizion, authOnevizion, projectOnevizion, headers, ''):
            if issue['VQS_IT_STATUS'] != "Ready for Review":
                log.info('No need to create a review for this issue - ' + str(issue['TRACKOR_KEY']))
            else:
                for revisionId in self.filteredRevisionList(authUpsource, urlUpsource, projectName, headers, issue['TRACKOR_KEY']):
                    url = urlUpsource + '~rpc/getRevisionReviewInfo'
                    data = {"projectId":projectName, "revisionId":revisionId['revisionId']}
                    answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
                    response = answer.json()
                    readble_json = response['result']['reviewInfo']

                    if readble_json != [{}]:
                        log.info('Review already exists')
                    else:
                        url = urlUpsource + '~rpc/createReview'
                        data = {"projectId":projectName, "revisions":revisionId['revisionId']}
                        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
                        log.info('Review for ' + str(issue['TRACKOR_KEY']) + ' created')

                        reviewId = self.reviewInfo(urlUpsource, authUpsource, projectName, revisionId['revisionId'], headers)
                        
                        self.addReviewLabel(authUpsource, urlUpsource, projectName, reviewId[0]['reviewInfo']['reviewId']['reviewId'], headers)
                        log.info('Label "ready for review" added to review ' + str(issue['TRACKOR_KEY']))

                        self.deleteReviewer(authUpsource, urlUpsource, projectName, reviewId[0]['reviewInfo']['reviewId']['reviewId'], headers)
                        log.info('Default reviewer deleted')
        log.info('Finished creating reviews')
        log.info('Finished upsource integration')

    #Returns the list of revisions that match the given search query
    def filteredRevisionList(self, authUpsource, urlUpsource, projectName, headers, issue):
        url = urlUpsource + '~rpc/getRevisionsListFiltered'
        data = {"projectId":projectName, "limit":1, "query":issue}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
        response = answer.json()
        readble_json = response['result']['revision']
        return readble_json

    #Removes a default reviewer from a review
    def deleteReviewer(self, authUpsource, urlUpsource, projectName, reviewId, headers):
        url = urlUpsource + '~rpc/removeParticipantFromReview'
        data = {"reviewId":{"projectId":projectName, "reviewId":reviewId}, "participant":{"userId":"653c3d2e-394f-4c6b-8757-3e070c78c910", "role":2}}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
        response = answer.json()
        return response

    #Adds a label to a review
    def addReviewLabel(self, authUpsource, urlUpsource, projectName, reviewId, headers):
        url = urlUpsource + '~rpc/addReviewLabel'
        data = {"projectId":projectName, "reviewId":{"projectId":projectName, "reviewId":reviewId}, "label":{"id":"ready", "name":"ready for review"}}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=authUpsource)
        response = answer.json()
        return response

    #Returns logging to stdout
    def get_logger(self, name=__file__, file='log.txt', encoding='utf-8'):
        log = logging.getLogger(name)
        log.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] %(filename)s:%(lineno)d %(levelname)-8s %(message)s')
        sh = logging.StreamHandler(stream=sys.stdout)
        sh.setFormatter(formatter)
        log.addHandler(sh)
        return log
