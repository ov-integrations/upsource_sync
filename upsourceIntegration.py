import requests
from requests.auth import HTTPBasicAuth
import json
import logging
import sys
import re
from datetime import datetime, timedelta

class Integration(object):

    def __init__(self, url_upsource="", login_upsource="", pass_upsource="", url_onevizion="", login_onevizion="", pass_onevizion="", project_name="", project_onevizion=""):
        self.url_upsource = url_upsource
        self.url_onevizion = url_onevizion
        self.project_name = project_name
        self.project_onevizion = project_onevizion

        self.auth_upsource = HTTPBasicAuth(login_upsource, pass_upsource)
        self.auth_onevizion = HTTPBasicAuth(login_onevizion, pass_onevizion)
        self.headers = {'Content-type':'application/json','Content-Encoding':'utf-8'}

        current_day = str((datetime.now()).strftime('%m/%d/%Y %H:%M'))
        current_day_datetime = datetime.strptime(current_day, '%m/%d/%Y %H:%M')
        self.previous_time = str((current_day_datetime - timedelta(minutes=15)).strftime('%m/%d/%Y %H:%M'))
        self.sysdate = str((datetime.now()).strftime('%m/%d/%Y'))
        self.next_two_week = str((datetime.now() + timedelta(days=14)).strftime('%m/%d/%Y'))
        self.log = self.get_logger()

        self.start_integration()

    def start_integration(self):
        self.log.info('Started upsource integration')

        issue_list = self.check_issue(self.project_onevizion, 'Ready for Review', '')

        for issue in issue_list:
            issue_id = issue['TRACKOR_ID']
            issue_title = issue['TRACKOR_KEY']
            issue_version_date = issue['Version.VER_REL_DATE']

            if "iOS" not in issue_title and "Android" not in issue_title:
                try:
                    revisions = self.filtered_revision_list(issue_title)
                except KeyError as e:
                    self.log.warning('Revisions are not found for Issue ID: [%s]' % issue_title)
                    self.log.warning('That key does not exist! [%s]' % str(e))
                    revisions = None
                except Exception as e:
                    self.log.warning('Revisions are not found for Issue ID: [%s]' % issue_title)

                    if hasattr(e, 'message'):
                        self.log.warning(e.message)
                    else:
                        self.log.warning(e)
                    revisions = None

                if revisions is not None:
                    review = self.get_reviews(issue_title)

                    if isinstance(review, list) and len(review) > 0 and 'reviewId' in review[0]:
                        review_status = review[0]['state']

                        if review_status == 2:
                            self.change_issue_status(revisions, review, issue_id, issue_title)
                    else:
                        self.create_review(revisions, issue_id, issue_title, issue_version_date)

        self.check_open_reviews()
        self.check_closed_reviews()

        self.log.info('Finished upsource integration')

    #Checks issue status
    def check_issue(self, project_onevizion, status, issue):
        url = self.url_onevizion + 'api/v3/trackor_types/Issue/trackors'
        data = {"fields":"TRACKOR_KEY, VQS_IT_STATUS, Version.VER_REL_DATE", "Product.TRACKOR_KEY":project_onevizion, "VQS_IT_STATUS":status, "TRACKOR_KEY":issue}
        answer = requests.get(url, headers=self.headers, params=data, auth=self.auth_onevizion)
        response = answer.json()
        return response

    #Returns the list of revisions that match the given search query
    def filtered_revision_list(self, query):
        url = self.url_upsource + '~rpc/getRevisionsListFiltered'
        data = {"projectId":self.project_name, "limit":100, "query":query}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        response = answer.json()
        readble_json = response['result']['revision']
        return readble_json

    def change_issue_status(self, revisions, review, issue_id, issue_title):
        review_updated_at = str(review[0]['updatedAt'])[:-3]
        update_date = str(datetime.fromtimestamp(int(review_updated_at)).strftime('%m/%d/%Y %H:%M'))
        review_id = review[0]['reviewId']['reviewId']

        branch_in_review = 'master'
        for revision in revisions:
            if 'branchHeadLabel' in revision:
                branch_in_review = revision['branchHeadLabel']
                branch_in_review_re = ''.join(branch_in_review)
                exclude_versions = re.search('^\d\d\.(\d\d$|\d$)', branch_in_review_re)
                if exclude_versions is None:
                    break

        if self.previous_time >= update_date:
            self.close_or_reopen_review(review_id, False)
            self.add_review_label(review_id, 'ready', 'ready for review')

            if branch_in_review != 'master':
                self.start_branch_tracking(review_id, branch_in_review)

            self.log.info('Review' + str(review_id) + ' reopened')

        else:
            if 'labels' in review:
                review_labels = review[0]['labels']

                for label in review_labels:
                    self.delete_review_label(review_id, label['id'], label['name'])

            if branch_in_review != 'master':
                self.stop_branch_tracking(branch_in_review, review_id)
                self.update_status(issue_id, issue_title, 'Ready for Merge')

            else:
                self.update_status(issue_id, issue_title, 'Ready for Test')

    #Create review
    def create_review(self, revisions, issue_id, issue_title, issue_version_date):
        for revision in revisions:
            if 'revisionCommitMessage' in revision:
                revision_title = revision['revisionCommitMessage']

                if 'Merge ' not in revision_title:
                    revision_id = revision['revisionId']
                    break

        url = self.url_upsource + '~rpc/createReview'
        data = {"projectId":self.project_name, "revisions":revision_id}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

        created_review = self.get_reviews(issue_title)
        review_id = created_review[0]['reviewId']['reviewId']

        self.add_review_label(review_id, 'ready', 'ready for review')
        self.delete_default_reviewer(review_id)
        self.add_url_to_issue(issue_id, review_id)

        self.log.info('Review for ' + str(issue_title) + ' created')

    #Removes a default reviewer from a review
    def delete_default_reviewer(self, review_id):
        url = self.url_upsource + '~rpc/removeParticipantFromReview'
        data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "participant":{"userId":"653c3d2e-394f-4c6b-8757-3e070c78c910", "role":2}}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Adds a review url to a issue
    def add_url_to_issue(self, issue_id, review_id):
        url = self.url_onevizion + 'api/v3/trackors/' + str(issue_id)
        data = {"I_CODE_REVIEW":self.url_upsource + self.project_name + "/review/" + review_id}
        requests.put(url, headers=self.headers, data=json.dumps(data), auth=self.auth_onevizion)

    #Returns review data
    def get_reviews(self, query):
        url = self.url_upsource + '~rpc/getReviews'
        data = {"projectId":self.project_name, "limit":100, "query":query}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        readble_json = answer.json()
        review = readble_json
        if 'reviews' in readble_json['result']:
            review = review['result']['reviews']
            return review
        else:
            return review

    #Change a review to a review for a branch
    def start_branch_tracking(self, review_id, branch):
        url = self.url_upsource + '~rpc/startBranchTracking'
        data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "branch":branch}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Adds a label to a review
    def add_review_label(self, review_id, label_id, label_name):
        url = self.url_upsource + '~rpc/addReviewLabel'
        data = {"projectId":self.project_name, "reviewId":{"projectId":self.project_name, "reviewId":review_id}, "label":{"id":label_id, "name":label_name}}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Delete a label to a review
    def delete_review_label(self, review_id, label_id, label_name):
        url = self.url_upsource + '~rpc/removeReviewLabel'
        data = {"projectId":self.project_name, "reviewId":{"projectId":self.project_name, "reviewId":review_id}, "label":{"id":label_id, "name":label_name}}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Close or reopen review
    def close_or_reopen_review(self, review_id, status):
        url = self.url_upsource + '~rpc/closeReview'
        data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "isFlagged":status}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Updates issue status
    def update_status(self, issue_id, issue_title, status):
        url = self.url_onevizion + 'api/v3/trackors/' + str(issue_id)
        data = {"VQS_IT_STATUS":status}
        requests.put(url, headers=self.headers, data=json.dumps(data), auth=self.auth_onevizion)

        self.log.info('Issue ' + str(issue_title) + ' updated status to ' + str(status))

    #Stops branch tracking for a given review
    def stop_branch_tracking(self, branch, review_id):
        url = self.url_upsource + '~rpc/stopBranchTracking'
        data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "branch":branch}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Close review if issue status = Ready for Test/Merge
    def check_open_reviews(self):
        review_list = self.get_reviews('state: open')
        for review_data in review_list:
            review_title = review_data['title']
            review_id = review_data['reviewId']['reviewId']

            issue_title = self.get_issue_title(review_title)
            issue = self.check_issue('', '', issue_title)

            if len(issue) > 0:
                issue_status = issue[0]['VQS_IT_STATUS']

                if issue_status in ['Ready for Test', 'Ready for Merge', 'Closed']:
                    self.close_or_reopen_review(review_id, True)

                    if 'labels' in review_data:
                        review_labels = review_data[0]['labels']
                        for label in review_labels:
                            self.delete_review_label(review_id, label['id'], label['name'])

                    if 'branch' in review_data:
                        branch_in_review = review_data[0]['branch']
                        self.stop_branch_tracking(branch_in_review, review_id)

                    self.log.info('Review ' + str(review_id) + ' closed')

                else:
                    issue_id = issue[0]['TRACKOR_ID']
                    issue_title = issue[0]['TRACKOR_KEY']
                    issue_version_date = issue[0]['Version.VER_REL_DATE']
                    review = self.get_reviews(issue_title)

                    self.setting_review(issue_id, issue_title, issue_version_date, review)

                    if issue_status == 'In Progress':
                        self.add_review_label(review_id, 'WIP', 'work in progress')
                        self.delete_review_label(review_id, 'ready', 'ready for review')

                    elif issue_status == 'Ready for Review':
                        self.delete_review_label(review_id, 'WIP', 'work in progress')

    #Returns issue title
    def get_issue_title(self, title):
        if 'Review of ' in title:
            start = title.find('Review of ')
            finish = title.find('-')
            issue_title = title[start+10:finish+7]

        else:
            issue_title = title[title.find('') : title.find(' ')]

        return issue_title

    #Setting review
    def setting_review(self, issue_id, issue_title, issue_version_date, review):
        review_status = review[0]['state']
        review_id = review[0]['reviewId']['reviewId']

        revision_list = self.filtered_revision_list(issue_title)

        if review_status == 1:
            review_participants = review[0]['participants']

            self.add_revision_to_review(review_id, issue_title)
            self.setting_participants(review_participants, review_id)
            self.setting_branch_tracking(revision_list, review_id)

            if issue_version_date != None:
                self.setting_current_release_label(issue_version_date, review_id)

    #Attaches a revision to a review
    def add_revision_to_review(self, review_id, issue_title):
        if "iOS" not in issue_title and "Android" not in issue_title:
            try:
                revision_list = self.filtered_revision_list(issue_title)
            except KeyError as e:
                self.log.warning('Revisions are not found for Issue ID: [%s]' % issue_title)
                self.log.warning('That key does not exist! [%s]' % str(e))
                revision_list = None
            except Exception as e:
                self.log.warning('Revisions are not found for Issue ID: [%s]' % issue_title)
                if hasattr(e, 'message'):
                    self.log.warning(e.message)
                else:
                    self.log.warning(e)
                revision_list = None

            if revision_list is not None:
                for revision in revision_list:
                    revision_id = revision['revisionId']
                    revision_title = revision['revisionCommitMessage']

                    if 'Merge ' not in revision_title:
                        url = self.url_upsource + '~rpc/addRevisionToReview'
                        data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "revisionId":revision_id}
                        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Added participants in review
    def setting_participants(self, review_participants, review_id):
        reviewer_id = ''
        for participant in review_participants:
            if participant['role'] == 1:
                author_id = participant['userId']

            if participant['role'] == 2:
                reviewer_id = participant['userId']

        if reviewer_id == '':
             self.get_review_file_extension(review_id, author_id)

    #Returns the code ownership summary for a given review
    def get_review_file_extension(self, review_id, author_id):
        url = self.url_upsource + '~rpc/getReviewOwnershipSummary'
        data = {"projectId":self.project_name, "reviewId":review_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        response = answer.json()
        changed_file  = response['result']

        file_list = []
        if 'files' in changed_file:
            change_list = changed_file['files']

            for diff_file in change_list:
                file_path = diff_file['filePath']
                file_extension = file_path[file_path.rfind('.')+1:]

                if file_extension in ['js', 'css', 'html', 'jsp', 'tag']:
                    file_extension = 'js'

                if file_extension not in file_list:
                    file_list.insert(0, file_extension)

                if 'sql' in file_list and 'java' in file_list and 'js' in file_list:
                    break

        self.add_reviewer(review_id, file_list, author_id)

    #Add a reviewer to the review
    def add_reviewer(self, review_id, file_list, author_id):
        user_id = ""

        for file_extension in file_list:
            if file_extension == 'sql':
                user_id = "840cb243-75a1-4bba-8fad-5859779db1df"
                self.log.info('Mikhail Knyazev added in reviewers')

            elif file_extension == 'java':
                user_id = "c7b9b297-d3e0-4148-af30-df20d676a0fd"
                self.log.info('Dmitry Nesmelov added in reviewers')

            elif file_extension in ['js', 'css', 'html', 'jsp', 'tag']:
                user_id = "9db3e4ca-5167-46b8-b114-5126af78d41c"
                self.log.info('Alex Yuzvyak added in reviewers')

            if user_id not in ["", author_id]:
                url = self.url_upsource + '~rpc/addParticipantToReview'
                data = {"reviewId":{"projectId":self.project_name, "reviewId":review_id}, "participant":{"userId":user_id, "role":2}}
                requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Start branch tracking if review in a branch
    def setting_branch_tracking(self, revision_list, review_id):
        for revision in revision_list:
            if 'branchHeadLabel' in revision:
                review_branch = revision['branchHeadLabel']
                review_branch_re = ''.join(review_branch)
                exclude_versions = re.search('^\d\d\.(\d\d$|\d$)', review_branch_re)
                if exclude_versions is None:
                    self.start_branch_tracking(review_id, review_branch)
                    break

    #Checks release date and adds or removes label
    def setting_current_release_label(self, issue_version_date, review_id):
        datetime_object = datetime.strptime(issue_version_date, '%Y-%m-%d')

        current_release = str((datetime_object - timedelta(days=4)).strftime('%m/%d/%Y'))

        if current_release > self.sysdate and current_release < self.next_two_week:
            self.add_review_label(review_id, '1ce36262-9d48-4b0e-93bd-d93722776e45', 'current release')

        elif current_release <= self.sysdate or current_release >= self.next_two_week:
            self.delete_review_label(review_id, '1ce36262-9d48-4b0e-93bd-d93722776e45', 'current release')

    #Removes labels from closed reviews and stop branch tracking
    def check_closed_reviews(self):
        labels_list = self.get_review_labels()

        label_names = ''
        for label in labels_list['predefinedLabels']:
            label_names = label_names + '{' + label['name'] + '}' + ','

        for label in labels_list['customLabels']:
            label_names = label_names + '{' + label['name'] + '}' + ','

        review_list = self.get_reviews('label: ' + label_names[:-1])
        for review_data in review_list:
            review_id = review_data['reviewId']['reviewId']
            review_status = review_data['state']

            if review_status == 2 and 'labels' in review_data:
                review_labels = review_data['labels']

                for label in review_labels:
                    self.delete_review_label(review_id, label['id'], label['name'])

        review_list = self.get_reviews('#track')
        for review_data in review_list:
            review_id = review_data['reviewId']['reviewId']
            review_status = review_data['state']

            if review_status == 2 and 'branch' in review_data:
                branch_in_review = review_data['branch']
                self.stop_branch_tracking(branch_in_review, review_id)

    def get_review_labels(self):
        url = self.url_upsource + '~rpc/getReviewLabels'
        data = {"projectId":self.project_name}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        response = answer.json()
        readble_json = response['result']
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
