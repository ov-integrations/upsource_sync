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
        self.work_with_review()

    #Create review if issue status = 'Ready for Review';
    #Close review if issue status = 'Ready for Test/Merge'
    def create_or_close_review(self):
        log = self.get_logger()
        log.info('Started upsource integration')
        log.info('Started creating reviews')

        for issue in self.check_issue(''):
            issue_id = issue['TRACKOR_ID']
            issue_title = issue['TRACKOR_KEY']
            issue_status = issue['VQS_IT_STATUS']

            revision_id = self.filtered_revision_list(issue_title, 0)

            if issue_status == 'Ready for Review':
                self.create_review(issue_id, issue_title, revision_id)

            elif issue_status in ['Ready for Test', 'Ready for Merge']:
                self.close_review(issue_title, revision_id)

        log.info('Finished creating reviews')

    #Create review
    def create_review(self, issue_id, issue_title, revision_id):
        log = self.get_logger()

        if 'revision' in revision_id:
            revision_id = revision_id['revision'][0]['revisionId']
            review_info = self.review_info(revision_id)

            if review_info == [{}]:
                url = self.url_upsource + '~rpc/createReview'
                data = {"projectId":self.project_name, "revisions":revision_id}
                requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
                
                review = self.review_info(revision_id)
                review_id = review[0]['reviewInfo']['reviewId']['reviewId']

                self.add_review_label(review_id, 'ready', 'ready for review')
                self.delete_default_reviewer(review_id)
                self.add_url_to_issue(issue_id, review_id)

                log.info('Review for ' + str(issue_title) + ' created')

    #Close review
    def close_review(self, issue_title, revision_id):
        log = self.get_logger()

        if 'revision' in revision_id:
            review_info = self.review_info(revision_id['revision'][0]['revisionId'])
            review = review_info[0]['reviewInfo']
            status = review['state']

            if review_info != [{}] and status != 2:
                review_id = review['reviewId']['reviewId']

                if 'labels' in review:
                    labels = review['labels']

                    for label in labels:
                        self.delete_review_label(review_id, label['id'], label['name'])

                self.stop_branch_tracking(review_info, review_id)
                self.close_or_reopen_review(review_id, True)

                log.info('Review for ' + str(issue_title) + ' closed')

    #Setting the review if the status = 1;
    #Updates task status if status = 2
    def work_with_review(self):
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
                review_id = review_info['reviewId']['reviewId']
                review_updated_at = review_info['updatedAt']
                participants = review_info['participants']

                created_at = str(review_info['createdAt'])[:-3]
                create_date = str(datetime.fromtimestamp(int(created_at)).strftime('%m/%d/%Y'))
                skip_number = skip_number + 1

                review_status = review_info['state']
                title = review_info['title']
                issue_title = self.get_issue_title(title)

                issue = self.check_issue(issue_title)
                issue_status = issue[0]['VQS_IT_STATUS']
                issue_version_date = issue[0]['Version.VER_REL_DATE']

                revision = self.filtered_revision_list("review: " + str(review_id), 0)
                revision_info = revision['revision'][0]
                revision_id = revision_info['revisionId']

                if 'branchHeadLabel' in revision_info:
                    branch_in_review = revision_info['branchHeadLabel'][0]

                else:
                    branch_in_review = 'master'

                if review_status == 1:
                    self.setting_review(revision_id, issue_title, issue_version_date, branch_in_review, participants)

                elif review_status == 2:
                    self.update_issue_status(review_id, review_updated_at, issue_status, issue_title, branch_in_review)

            else:
                break

        log.info('Finished updating the status of issues')
        log.info('Finished upsource integration')

    #Setting new review
    def setting_review(self, revision_id, issue_title, issue_version_date, branch_in_review, participants):
        created_review_info = self.review_info(revision_id)
        review_id = created_review_info[0]['reviewInfo']['reviewId']['reviewId']

        reviewer_id = ''
        for participant in participants:
            if participant['role'] == 1:
                author_id = participant['userId']

            if participant['role'] == 2:
                reviewer_id = participant['userId']

        if branch_in_review != 'master':
            self.start_branch_tracking(review_id, branch_in_review)

        if issue_version_date != None:
            self.current_release_label(review_id, issue_version_date)

        self.add_revision_to_review(review_id, issue_title)

        if reviewer_id == '':
             self.get_revision_file_extension(review_id, revision_id, author_id)

    #Updated issue status; reopen review if issue status == 'Ready for Review'
    def update_issue_status(self, review_id, review_updated_at, issue_status, issue_title, branch_in_review):
        sysdate = datetime.now()
        updated_at = str(review_updated_at)[:-3]
        update_date = str(datetime.fromtimestamp(int(updated_at)).strftime('%m/%d/%Y %H:%M'))
        current_day = str(sysdate.strftime('%m/%d/%Y %H:%M'))
        current_day_datetime = datetime.strptime(current_day, '%m/%d/%Y %H:%M')
        previous_hours = str((current_day_datetime - timedelta(hours=1)).strftime('%m/%d/%Y %H:%M'))

        if previous_hours >= update_date and issue_status == 'Ready for Review':
            self.close_or_reopen_review(review_id, False)

            self.add_review_label(review_id, 'ready', 'ready for review')

            if branch_in_review != 'master':
                self.start_branch_tracking(review_id, branch_in_review)

        if branch_in_review != 'master':
            self.update_status(issue_title, 'Ready for Merge')

        elif branch_in_review == 'master':
            self.update_status(issue_title, 'Ready for Test')

    #Returns a list of reviews for the last 30 days
    def get_reviews(self, skip_number):
        url = self.url_upsource + '~rpc/getReviews'
        data = {"projectId":self.project_name, "limit":1, "skip":skip_number, "sortBy":"id,desc"}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        readble_json = answer.json()
        review = readble_json['result']
        return review

    #Returns issue title
    def get_issue_title(self, title):
        if 'Review of ' in title:
            start = title.find('Review of ')
            finish = title.find('-')
            issue_title = title[start+10:finish+7]

        else:
            issue_title = title[title.find('') : title.find(' ')]

        return issue_title

    #Updates issue status
    def update_status(self, issue_title, status):
        log = self.get_logger()
        issue = self.check_issue(issue_title)

        if issue != []:

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
            data = {"fields":"TRACKOR_KEY, VQS_IT_STATUS, Version.VER_REL_DATE", "TRACKOR_KEY":issue_title, "Product.TRACKOR_KEY":self.project_onevizion}
            answer = requests.get(url, headers=self.headers, params=data, auth=self.auth_onevizion)
            response = answer.json()
            return response

    #Returns the list of revisions that match the given search query
    def filtered_revision_list(self, query, skip_number):
        url = self.url_upsource + '~rpc/getRevisionsListFiltered'
        data = {"projectId":self.project_name, "limit":1, "query":query, "skip":skip_number}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        response = answer.json()
        readble_json = response['result']
        return readble_json

    #Returns short review information for a set of revisions
    def review_info(self, revision_id):
        url = self.url_upsource + '~rpc/getRevisionReviewInfo'
        data = {"projectId":self.project_name, "revisionId":revision_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        response = answer.json()
        readble_json = response['result']['reviewInfo']
        return readble_json

    #Change a review to a review for a branch
    def start_branch_tracking(self, review_id, branch):
        url = self.url_upsource + '~rpc/startBranchTracking'
        data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "branch":branch}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Stops branch tracking for a given review
    def stop_branch_tracking(self, review_info, review_id):
        if 'branch' in review_info:
            branch = reviewInfo['branch']

            url = self.url_upsource + '~rpc/stopBranchTracking'
            data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "branch":branch}
            requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Checks release date and adds or removes label
    def current_release_label(self, review_id, issue_version_date):
        sysdate = datetime.now()
        datetime_object = datetime.strptime(issue_version_date, '%Y-%m-%d')

        current_release = str((datetime_object - timedelta(days=4)).strftime('%m/%d/%Y'))

        if current_release > str(sysdate.strftime('%m/%d/%Y')):
            self.add_review_label(review_id, '1ce36262-9d48-4b0e-93bd-d93722776e45', 'current release')

        elif current_release <= str(sysdate.strftime('%m/%d/%Y')):
            self.delete_review_label(review_id, '1ce36262-9d48-4b0e-93bd-d93722776e45', 'current release')

    #Adds a label to a review
    def add_review_label(self, review_id, label_id, label_name):
        url = self.url_upsource + '~rpc/addReviewLabel'
        data = {"projectId":self.project_name, "reviewId":{"projectId":self.project_name, "reviewId":review_id}, "label":{"id":label_id, "name":label_name}}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Removes a default reviewer from a review
    def delete_default_reviewer(self, review_id):
        url = self.url_upsource + '~rpc/removeParticipantFromReview'
        data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "participant":{"userId":"653c3d2e-394f-4c6b-8757-3e070c78c910", "role":2}}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Attaches a revision to a review
    def add_revision_to_review(self, review_id, issue_title):
        skip_number = 0
        while skip_number != None:
            revision_list = self.filtered_revision_list(issue_title, skip_number)

            if 'revision' in revision_list:
                skip_number = skip_number + 1
                revision_id = revision_list['revision'][0]['revisionId']
                revision_title = revision_list['revision'][0]['revisionCommitMessage']

                if 'Merge ' not in revision_title:
                    url = self.url_upsource + '~rpc/addRevisionToReview'
                    data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "revisionId":revision_id}
                    requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

            else:
                skip_number = None

    #Returns the list of changes (files that were added, removed, or modified) in a revision
    def get_revision_file_extension(self, review_id, revision_id, author_id):
        skip_number = 0
        file_list = []
        while skip_number != None:
            url = self.url_upsource + '~rpc/getRevisionChanges'
            data = {"revision":{"projectId":self.project_name, "revisionId":revision_id}, "limit":1, "skip":skip_number}
            answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
            response = answer.json()
            changed_file  = response['result']

            if 'diff' in changed_file:
                skip_number = skip_number + 1
                diff_file = changed_file['diff']
                file_extension = diff_file[0]['fileIcon'][5:]

                if file_extension in ['js', 'css', 'html', 'jsp', 'tag']:
                    file_extension = 'js'

                if file_extension not in file_list:
                    file_list.insert(0, file_extension)

                if 'sql' in file_list and 'java' in file_list and 'js' in file_list:
                    break

            else:
                skip_number = None

        self.add_reviewer(review_id, file_list, author_id)

    #Add a reviewer to the review
    def add_reviewer(self, review_id, file_list, author_id):
        log = self.get_logger()

        user_id = ""

        for file_extension in file_list:
            if file_extension == 'sql':
                user_id = "840cb243-75a1-4bba-8fad-5859779db1df"
                log.info('Mikhail Knyazev added in reviewers')

            elif file_extension == 'java':
                user_id = "c7b9b297-d3e0-4148-af30-df20d676a0fd"
                log.info('Dmitry Nesmelov added in reviewers')

            elif file_extension in ['js', 'css', 'html', 'jsp', 'tag']:
                user_id = "9db3e4ca-5167-46b8-b114-5126af78d41c"
                log.info('Alex Yuzvyak added in reviewers')

            if user_id not in ["", author_id]:
                url = self.url_upsource + '~rpc/addParticipantToReview'
                data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "participant":{"userId":user_id, "role":2}}
                requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Adds a review url to a issue
    def add_url_to_issue(self, issue_id, review_id):
        url = self.url_onevizion + 'api/v3/trackors/' + str(issue_id)
        data = {"I_CODE_REVIEW":self.url_upsource + self.project_name + "/review/" + review_id}
        requests.put(url, headers=self.headers, data=json.dumps(data), auth=self.auth_onevizion)

    #Close review
    def close_or_reopen_review(self, review_id, status):
        url = self.url_upsource + '~rpc/closeReview'
        data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "isFlagged":status}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Delete a label to a review
    def delete_review_label(self, review_id, label_id, label_name):
        url = self.url_upsource + '~rpc/removeReviewLabel'
        data = {"projectId":self.project_name, "reviewId":{"projectId":self.project_name, "reviewId":review_id}, "label":{"id":label_id, "name":label_name}}
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
