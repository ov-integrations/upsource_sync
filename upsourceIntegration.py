import requests
from requests.auth import HTTPBasicAuth
import json
import logging
import sys
from datetime import datetime, timedelta

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

        self.auth_upsource = HTTPBasicAuth(login_upsource, pass_upsource)
        self.auth_onevizion = HTTPBasicAuth(login_onevizion, pass_onevizion)
        self.headers = {'Content-type':'application/json','Content-Encoding':'utf-8'}

        self.create_or_close_review()
        self.update_issue_status()

    def update_issue_status(self):
        log = self.get_logger()
        log.info('Started updating the status of issues')

        skip_number = 0
        sysdate = datetime.now()
        previous_month = str((sysdate - timedelta(days=30)).strftime('%m/%d/%Y'))
        create_date = str(sysdate.strftime('%m/%d/%Y'))
        while create_date >= previous_month:
            review = self.get_reviews(skip_number)

            if 'reviews' in review:
                review_info = review['reviews'][0]

                created_at = str(review_info['createdAt'])[:-3]
                create_date = str(datetime.fromtimestamp(int(created_at)).strftime('%m/%d/%Y'))
                skip_number = skip_number + 1

                status = review_info['state']
                review_id = review_info['reviewId']['reviewId']
                title = review_info['title']
                issue_title = self.get_issue_title(title)

                if 'branch' in review_info and status == 2:
                    branch = review_info['branch']
                    self.update_status(issue_title, 'Ready for Merge')

                elif 'branch' not in review_info and status == 2:
                    self.update_status(issue_title, 'Ready for Test')

            else:
                break

        log.info('Finished updating the status of issues')
        log.info('Finished upsource integration')

    #Returns a list of reviews for the last 30 days
    def get_reviews(self, skip_number):
        url = self.url_upsource + '~rpc/getReviews'
        data = {"projectId":self.project_name, "limit":1, "skip":skip_number}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        readble_json = answer.json()
        review = readble_json['result']
        return review

    #Returns issue title
    def get_issue_title(self, title):
        if 'Review of ' in title:
            issue_title = title[title.find('Review of ') : title.find('-',2)]

        else:
            issue_title = title[title.find('') : title.find(' ')]

        return issue_title

    #Updates issue status
    def update_status(self, issue_title, status):
        log = self.get_logger()

        issue = self.check_issue(issue_title)
        if issue[0]['VQS_IT_STATUS'] == 'Ready for Review' and status == 'Ready for Merge':
            url = self.url_onevizion + 'api/v3/trackors/' + str(issue[0]['TRACKOR_ID'])
            data = {"VQS_IT_STATUS":status}
            requests.put(url, headers=self.headers, data=json.dumps(data), auth=self.auth_onevizion)

            log.info('Issue ' + issue[0]['TRACKOR_KEY'] + ' updated status to "Ready for Merge"')

        elif issue[0]['VQS_IT_STATUS'] == 'Ready for Review' and status == "Ready for Test":
            url = self.url_onevizion + 'api/v3/trackors/' + str(issue[0]['TRACKOR_ID'])
            data = {"VQS_IT_STATUS":status}
            requests.put(url, headers=self.headers, data=json.dumps(data), auth=self.auth_onevizion)

            log.info('Issue ' + issue[0]['TRACKOR_KEY'] + ' updated status to "Ready for Test"')

    #Checks issue status
    def check_issue(self, issue_title):
        if issue_title == '':
            url = self.url_onevizion + 'api/v3/trackor_types/Issue/trackors'
            data = {"fields":"TRACKOR_KEY, VQS_IT_STATUS", "Product.TRACKOR_KEY":self.project_onevizion}
            answer = requests.get(url, headers=self.headers, params=data, auth=self.auth_onevizion)
            response = answer.json()
            return response

        else:
            url = self.url_onevizion + 'api/v3/trackor_types/Issue/trackors'
            data = {"fields":"TRACKOR_KEY, VQS_IT_STATUS", "TRACKOR_KEY":issue_title, "Product.TRACKOR_KEY":self.project_onevizion}
            answer = requests.get(url, headers=self.headers, params=data, auth=self.auth_onevizion)
            response = answer.json()
            return response

    #Create review if issue status = 'Ready for Review';
    #Close review if issue status = 'Ready for Test/Merge'
    def create_or_close_review(self):
        log = self.get_logger()
        log.info('Started upsource integration')
        log.info('Started creating reviews')

        for issue in self.check_issue(''):
            issue_title = issue['TRACKOR_KEY']
            issue_status = issue['VQS_IT_STATUS']

            if issue_status in ['Ready for Review', 'Ready for Test', 'Ready for Merge']:

                if issue_status == "Ready for Review":
                    revision_id = self.check_review(issue_title)

                else:
                    revision_id = self.filtered_revision_list(issue_title, 0)
                    review_info = self.review_info(revision_id['revision'][0]['revisionId'])

                    if review_info != [{}]:
                        review_id = review_info[0]['reviewInfo']['reviewId']['reviewId']

                        self.close_review(review_id)
                        log.info('Review for ' + str(issue_title) + ' closed')

        log.info('Finished creating reviews')

    #If there is a review, then revisions are added to this review;
    #If there is no review, then create a review
    def check_review(self, issue_title):
        skip_number = 0
        review_info_returned = ''
        while skip_number != None:
            revision_id = self.filtered_revision_list(issue_title, skip_number)

            if 'revision' in revision_id:
                revision = revision_id['revision'][0]
                review_info = self.review_info(revision['revisionId'])[0]

                if review_info != [{}]:
                    review_id = review_info['reviewInfo']['reviewId']['reviewId']
                    self.add_revision_to_review(issue_title, review_id)

                    if 'reviewInfo' in review_info:
                        review_status = review_info['reviewInfo']['state']
                        self.branch_review(revision, review_status, review_id)

                    skip_number = None

                else:
                    revision_info_returned = revision_id['revision'][0]
                    self.setting_new_review(revision_info_returned, issue_title)

                    skip_number = skip_number + 1

            else:
                skip_number = None

    #Returns the list of revisions that match the given search query
    def filtered_revision_list(self, issue, skip_number):
        url = self.url_upsource + '~rpc/getRevisionsListFiltered'
        data = {"projectId":self.project_name, "limit":1, "query":issue, "skip":skip_number}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        response = answer.json()
        readble_json = response['result']
        return readble_json

    #Setting new review
    def setting_new_review(self, revision_info_returned, issue_title):
        log = self.get_logger()
        revision_id = revision_info_returned['revisionId']
        revision = revision_info_returned

        self.create_review(revision_id)
        log.info('Review for ' + str(issue_title) + ' created')
        
        created_review_info = self.review_info(revision_id)
        review_id = created_review_info[0]['reviewInfo']['reviewId']['reviewId']
        review_branche = self.revision_branch(revision_id)
        review_status = created_review_info[0]['reviewInfo']['state']

        self.branch_review(revision, review_status, review_id)

        self.add_review_label(review_id)
        log.info('Label "ready for review" added to review ' + str(issue_title))

        self.delete_default_reviewer(review_id)
        log.info('Default reviewer deleted')

        self.add_reviewer(review_id, revision_id)

        self.add_revision_to_review(issue_title, review_id)

    #Create review
    def create_review(self, revision_id):
        url = self.url_upsource + '~rpc/createReview'
        data = {"projectId":self.project_name, "revisions":revision_id}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Returns short review information for a set of revisions
    def review_info(self, revision_id):
        url = self.url_upsource + '~rpc/getRevisionReviewInfo'
        data = {"projectId":self.project_name, "revisionId":revision_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        response = answer.json()
        readble_json = response['result']['reviewInfo']
        return readble_json

    #Returns the list of branches a revision is part of
    def revision_branch(self, revision_id):
        url = self.url_upsource + '~rpc/getRevisionBranches'
        data = {"projectId":self.project_name, "revisionId":revision_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        response = answer.json()
        readble_json = response['result']['branchName']
        return readble_json

    #Change a review to a review for a branch
    def branch_review(self, revision, review_status, review_id):
        if 'branchHeadLabel' in revision:
            branch = revision['branchHeadLabel'][0]

            if review_status == 1 and branch != 'master':
                url = self.url_upsource + '~rpc/startBranchTracking'
                data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "branch":branch}
                requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Adds a label to a review
    def add_review_label(self, review_id):
        url = self.url_upsource + '~rpc/addReviewLabel'
        data = {"projectId":self.project_name, "reviewId":{"projectId":self.project_name, "reviewId":review_id}, "label":{"id":"ready", "name":"ready for review"}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        response = answer.json()
        return response

    #Removes a default reviewer from a review
    def delete_default_reviewer(self, review_id):
        url = self.url_upsource + '~rpc/removeParticipantFromReview'
        data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "participant":{"userId":"653c3d2e-394f-4c6b-8757-3e070c78c910", "role":2}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        response = answer.json()
        return response

    #Add a reviewer to the review
    def add_reviewer(self, review_id, revision_id):
        log = self.get_logger()

        user_id = ""
        for revision_file_extension in self.get_revision_file_extension(revision_id):
            file_extension = revision_file_extension['fileIcon'][5:]

            if file_extension == 'sql':
                user_id = "840cb243-75a1-4bba-8fad-5859779db1df"
                log.info('Mikhail Knyazev added in reviewers')

            elif file_extension == 'java':
                user_id = "c7b9b297-d3e0-4148-af30-df20d676a0fd"
                log.info('Dmitry Nesmelov added in reviewers')

            elif file_extension in ['js', 'css', 'html']:
                user_id = "9db3e4ca-5167-46b8-b114-5126af78d41c"
                log.info('Alex Yuzvyak added in reviewers')

            if user_id != "":
                url = self.url_upsource + '~rpc/addParticipantToReview'
                data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "participant":{"userId":user_id, "role":2}}
                requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Returns the list of changes (files that were added, removed, or modified) in a revision
    def get_revision_file_extension(self, revision_id):
        url = self.url_upsource + '~rpc/getRevisionChanges'
        data = {"revision":{"projectId":self.project_name, "revisionId":revision_id}, "limit":10}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        response = answer.json()
        readble_json = response['result']['diff']
        unique_file_extension = {file_extension['fileIcon']:file_extension for file_extension in readble_json}.values()
        return unique_file_extension

    #Attaches a revision to a review
    def add_revision_to_review(self, issue_title, review_id):
        skip_number = 0
        while skip_number != None:
            revision_list = self.filtered_revision_list(issue_title, skip_number)

            if 'revision' in revision_list:
                skip_number = skip_number + 1
                revision_id = revision_list['revision'][0]['revisionId']

                url = self.url_upsource + '~rpc/addRevisionToReview'
                data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "revisionId":revision_id}
                requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

            else:
                skip_number = None

    #Close review
    def close_review(self, review_id):
        url = self.url_upsource + '~rpc/closeReview'
        data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "isFlagged":True}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Returns logging to stdout
    def get_logger(self, name=__file__, file='log.txt', encoding='utf-8'):
        log = logging.getLogger(name)
        log.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] %(filename)s:%(lineno)d %(levelname)-8s %(message)s')
        sh = logging.StreamHandler(stream=sys.stdout)
        sh.setFormatter(formatter)
        log.addHandler(sh)
        return log
