import requests
from requests.auth import HTTPBasicAuth
import json
import logging
import sys

class Integration(object):

    def __init__(self, url_upsource="", login_upsource="", pass_upsource="", url_onevizion="", login_onevizion="", pass_onevizion="", project_name="", project_onevizion=""):
        self.url_upsource = url_upsource
        self.login_upsource = login_upsource
        self.pass_upsource = pass_upsource
        self.url_onevizion = url_onevizion
        self.login_onevizion = login_onevizion
        self.pass_onevizion = pass_onevizion
        self.project_name = project_name
        self.project_onevizion = project_onevizion
        
        auth_upsource = HTTPBasicAuth(login_upsource, pass_upsource)
        auth_onevizion = HTTPBasicAuth(login_onevizion, pass_onevizion)
        headers = {'Content-type':'application/json','Content-Encoding':'utf-8'}

        #self.revision_list(url_onevizion, auth_onevizion, url_upsource, auth_upsource, project_name, project_onevizion, headers)
        self.create_review(url_onevizion, auth_onevizion, url_upsource, auth_upsource, project_name, project_onevizion, headers)

    #Returns the list of revisions in a given project
    def revision_list(self, url_onevizion, auth_onevizion, url_upsource, auth_upsource, project_name, project_onevizion, headers):
        log = self.get_logger()
        log.info('Started upsource integration')
        log.info('Started updating the status of issues')

        skip_number = 0
        while skip_number != None:
            url = url_upsource + '~rpc/getRevisionsList'
            data = {"projectId":project_name, "limit":1, "skip":skip_number}
            answer = requests.post(url, headers=headers, data=json.dumps(data), auth=auth_upsource)
            response = answer.json()
            readble_json = response['result']

            if 'revision' in readble_json:
                skip_number = skip_number + 1
                revision_id = readble_json['revision'][0]['revisionId']

                review_info = self.review_info(url_upsource, auth_upsource, project_name, revision_id, headers)

                if review_info == [{}]:
                    print('This revision has no review')
                else:
                    review_title = self.get_issue_title(review_info[0]['reviewInfo']['title'])
                    review_status = review_info[0]['reviewInfo']['state']
                    review_branche = self.revision_branche(url_upsource, auth_upsource, project_name, headers, revision_id)

                    self.check_status(url_onevizion, auth_onevizion, project_onevizion, headers, review_title, review_status, review_branche)
            else:
                skip_number = None
        log.info('Finished updating the status of issues')

    #Returns short review information for a set of revisions
    def review_info(self, url_upsource, auth_upsource, project_name, revision_id, headers):
        url = url_upsource + '~rpc/getRevisionReviewInfo'
        data = {"projectId":project_name, "revisionId":revision_id}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=auth_upsource)
        response = answer.json()
        readble_json = response['result']['reviewInfo']
        return readble_json

    #Returns issue title
    def get_issue_title(self, issue_title):
        if 'Revert \"' in issue_title:
            return None
        elif 'Review of ' in issue_title:
            return None
        elif 'Merge branch \"' in issue_title:
            return None
        elif 'Merge branch \'master\' into ' in issue_title:
            return None
        else:
            return issue_title[issue_title.find('') : issue_title.find(' ')]
    
    #Returns the list of branches a revision is part of
    def revision_branche(self, url_upsource, auth_upsource, project_name, headers, revision_id):
        url = url_upsource + '~rpc/getRevisionBranches'
        data = {"projectId":project_name, "revisionId":revision_id}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=auth_upsource)
        response = answer.json()
        readble_json = response['result']['branchName']
        return readble_json
    
    #Checks review status and run update_issue
    def check_status(self, url_onevizion, auth_onevizion, project_onevizion, headers, issue, status, branch):
        log = self.get_logger()
        if issue == 'None':
            return None
        else:
            if status == 2 and branch == 'master':
                self.update_issue(url_onevizion, auth_onevizion, project_onevizion, headers, issue, 'Ready for Merge')
            elif status == 2 and branch != 'master':
                self.update_issue(url_onevizion, auth_onevizion, project_onevizion, headers, issue, 'Ready for Test')
            else: log.info('Review ' + str(issue) + ' is not yet closed')

    #Updates issue status if review status = 2 (closed)
    def update_issue(self, url_onevizion, auth_onevizion, project_onevizion, headers, issue, status):
        log = self.get_logger()

        issue_title = self.check_issue(url_onevizion, auth_onevizion, project_onevizion, headers, issue)
        if issue_title['VQS_IT_STATUS'] == 'Ready for Review' and status == 'Ready for Merge':
            url = url_onevizion + 'api/v3/trackors/' + str(issue_title['TRACKOR_ID'])
            data = {"VQS_IT_STATUS":status}
            requests.put(url, headers=headers, data=json.dumps(data), auth=auth_onevizion)
            log.info('Issue ' + issue_title['TRACKOR_KEY'] + ' updated status to "Ready for Merge"')
        elif issue_title['VQS_IT_STATUS'] == 'Ready for Review' and status == "Ready for Test":
            url = url_onevizion + 'api/v3/trackors/' + str(issue_title['TRACKOR_ID'])
            data = {"VQS_IT_STATUS":status}
            requests.put(url, headers=headers, data=json.dumps(data), auth=auth_onevizion)
            log.info('Issue ' + issue_title['TRACKOR_KEY'] + ' updated status to "Ready for Test"')
        else: log.info('Issue ' + issue_title['TRACKOR_KEY'] + ' has already been updated')

    #Checks issue status
    def check_issue(self, url_onevizion, auth_onevizion, project_onevizion, headers, issue):
        if issue == '':
            url = url_onevizion + 'api/v3/trackor_types/Issue/trackors'
            params = {"fields":"TRACKOR_KEY, VQS_IT_STATUS, Product.TRACKOR_KEY", "Product.TRACKOR_KEY":project_onevizion}
            answer = requests.get(url, headers=headers, params=params, auth=auth_onevizion)
            response = answer.json()
            return response
        else:
            url = url_onevizion + 'api/v3/trackor_types/Issue/trackors'
            params = {"fields":"TRACKOR_KEY, VQS_IT_STATUS, Product.TRACKOR_KEY", "TRACKOR_KEY":issue, "Product.TRACKOR_KEY":project_onevizion}
            answer = requests.get(url, headers=headers, params=params, auth=auth_onevizion)
            response = answer.json()
            return response

    #Creates review if issue status = 'Ready for Review'
    def create_review(self, url_onevizion, auth_onevizion, url_upsource, auth_upsource, project_name, project_onevizion, headers):
        log = self.get_logger()
        log.info('Started creating reviews')
        for issue in self.check_issue(url_onevizion, auth_onevizion, project_onevizion, headers, ''):
            if issue['VQS_IT_STATUS'] != "Ready for Review":
                log.info('No need to create a review for this issue - ' + str(issue['TRACKOR_KEY']))
            else:
                for revision_id in self.filtered_revision_list(auth_upsource, url_upsource, project_name, headers, issue['TRACKOR_KEY']):
                    review_info = self.review_info(url_upsource, auth_upsource, project_name, revision_id['revisionId'], headers)
                    
                    if review_info != [{}]:
                        log.info('Review already exists')
                    else:
                        url = url_upsource + '~rpc/createReview'
                        data = {"projectId":project_name, "revisions":revision_id['revisionId']}
                        requests.post(url, headers=headers, data=json.dumps(data), auth=auth_upsource)
                        log.info('Review for ' + str(issue['TRACKOR_KEY']) + ' created')

                        review_id = self.review_info(url_upsource, auth_upsource, project_name, revision_id['revisionId'], headers)
                        
                        self.add_review_label(auth_upsource, url_upsource, project_name, review_id[0]['reviewInfo']['reviewId']['reviewId'], headers)
                        log.info('Label "ready for review" added to review ' + str(issue['TRACKOR_KEY']))

                        self.delete_reviewer(auth_upsource, url_upsource, project_name, review_id[0]['reviewInfo']['reviewId']['reviewId'], headers)
                        log.info('Default reviewer deleted')

                        for file_extension in self.get_revision_file_extension(auth_upsource, url_upsource, project_name, revision_id['revisionId'], headers):

                            if file_extension['fileIcon'][5:] == 'sql':
                                self.add_reviewer(auth_upsource, url_upsource, project_name, review_id[0]['reviewInfo']['reviewId']['reviewId'], "840cb243-75a1-4bba-8fad-5859779db1df", headers)
                                log.info('Mikhail Knyazev added in reviewers')

                            elif file_extension['fileIcon'][5:] == 'java':
                                self.add_reviewer(auth_upsource, url_upsource, project_name, review_id[0]['reviewInfo']['reviewId']['reviewId'], "c7b9b297-d3e0-4148-af30-df20d676a0fd", headers)
                                log.info('Dmitry Nesmelov added in reviewers')

                            elif file_extension['fileIcon'][5:] == ['js', 'css', 'html']:
                                self.add_reviewer(auth_upsource, url_upsource, project_name, review_id[0]['reviewInfo']['reviewId']['reviewId'], "9db3e4ca-5167-46b8-b114-5126af78d41c", headers)
                                log.info('Alex Yuzvyak added in reviewers')

        log.info('Finished creating reviews')
        log.info('Finished upsource integration')

    #Returns the list of revisions that match the given search query
    def filtered_revision_list(self, auth_upsource, url_upsource, project_name, headers, issue):
        url = url_upsource + '~rpc/getRevisionsListFiltered'
        data = {"projectId":project_name, "limit":1, "query":issue}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=auth_upsource)
        response = answer.json()
        readble_json = response['result']['revision']
        return readble_json

    #Returns the list of changes (files that were added, removed, or modified) in a revision
    def get_revision_file_extension(self, auth_upsource, url_upsource, project_name, revision_id, headers):
        url = url_upsource + '~rpc/getRevisionChanges'
        data = {"revision":{"projectId":project_name, "revisionId":revision_id}, "limit":10}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=auth_upsource)
        response = answer.json()
        readble_json = response['result']['diff']
        unique = {each['fileIcon']:each for each in readble_json}.values()
        return unique

    #Removes a default reviewer from a review
    def add_reviewer(self, auth_upsource, url_upsource, project_name, review_id, user_id, headers):
        url = url_upsource + '~rpc/addParticipantToReview'
        data = {"reviewId":{"projectId":project_name, "reviewId":review_id}, "participant":{"userId":user_id, "role":2}}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=auth_upsource)
        response = answer.json()
        return response

    #Removes a default reviewer from a review
    def delete_reviewer(self, auth_upsource, url_upsource, project_name, review_id, headers):
        url = url_upsource + '~rpc/removeParticipantFromReview'
        data = {"reviewId":{"projectId":project_name, "reviewId":review_id}, "participant":{"userId":"653c3d2e-394f-4c6b-8757-3e070c78c910", "role":2}}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=auth_upsource)
        response = answer.json()
        return response

    #Adds a label to a review
    def add_review_label(self, auth_upsource, url_upsource, project_name, review_id, headers):
        url = url_upsource + '~rpc/addReviewLabel'
        data = {"projectId":project_name, "reviewId":{"projectId":project_name, "reviewId":review_id}, "label":{"id":"ready", "name":"ready for review"}}
        answer = requests.post(url, headers=headers, data=json.dumps(data), auth=auth_upsource)
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
