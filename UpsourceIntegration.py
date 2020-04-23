import requests
from requests.auth import HTTPBasicAuth
import json
import logging
import sys
import re
import onevizion
from datetime import datetime, timedelta

class Integration(object):

    def __init__(self, url_upsource="", login_upsource="", pass_upsource="", project_upsource="", departments="",
                     url_onevizion="", login_onevizion="", pass_onevizion="", product_onevizion="", trackor_type=""):
        self.url_upsource = self.url_setting(url_upsource)        
        self.project_upsource = project_upsource
        self.auth_upsource = HTTPBasicAuth(login_upsource, pass_upsource)
        self.departments = departments

        self.url_onevizion = self.url_setting(url_onevizion)
        self.product_onevizion = product_onevizion
        self.trackor_type = trackor_type
        self.issue_list_request = onevizion.Trackor(trackorType=self.trackor_type, URL=self.url_onevizion, userName=login_onevizion, password=pass_onevizion)

        self.headers = {'Content-type':'application/json','Content-Encoding':'utf-8'}
        self.log = self.get_logger()

    def start_integration(self):
        self.log.info('Started upsource integration')

        issue_list = self.check_issue('Ready for Review')

        for issue in issue_list:
            self.issue_id = issue['TRACKOR_ID']
            self.issue_title = issue['TRACKOR_KEY']
            self.issue_summary = issue['VQS_IT_XITOR_NAME']

            revision_list = self.check_revision()

            if revision_list is not None and 'revision' in revision_list:
                revision_in_revision_list = revision_list['revision']
                review = self.get_reviews(self.issue_title)

                if isinstance(review, list) and len(review) > 0 and 'reviewId' in review[0]:
                    review_status = review[0]['state']

                    if review_status == 2:
                        self.change_issue_status(review)
                else:
                    self.create_review(revision_in_revision_list)

        self.check_open_reviews()
        self.check_closed_reviews()

        self.log.info('Finished upsource integration')

    #Checks issue status
    def check_issue(self, status):
        if status == '':
            self.issue_list_request.read(
                filters={'Product.TRACKOR_KEY':self.product_onevizion,'TRACKOR_KEY':self.issue_title},
                fields=['TRACKOR_KEY', 'VQS_IT_STATUS', 'Version.VER_UAT_DATE']
                )
        else:
            self.issue_list_request.read(
                filters={'Product.TRACKOR_KEY':self.product_onevizion,'VQS_IT_STATUS':status},
                fields=['TRACKOR_KEY', 'VQS_IT_STATUS', 'VQS_IT_XITOR_NAME']
                )
        response = self.issue_list_request.jsonData
        return response

    def check_revision(self):
        try:
            revision_list = self.filtered_revision_list()
        except KeyError as e:
            self.log.warning('Revisions are not found for Issue ID: [%s]' % self.issue_title)
            self.log.warning('That key does not exist! [%s]' % str(e))
            revision_list = None
        except Exception as e:
            self.log.warning('Revisions are not found for Issue ID: [%s]' % self.issue_title)

            if hasattr(e, 'message'):
                self.log.warning(e.message)
            else:
                self.log.warning(e)
            revision_list = None

        return revision_list

    #Returns the list of revisions that match the given search query
    def filtered_revision_list(self):
        url = self.url_upsource + '~rpc/getRevisionsListFiltered'
        data = {"projectId":self.project_upsource, "limit":100, "query":self.issue_title}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        return answer.json()['result']

    def change_issue_status(self, review):
        review_updated_at = str(review[0]['updatedAt'])[:-3]
        update_date = str(datetime.fromtimestamp(int(review_updated_at)).strftime('%m/%d/%Y %H:%M'))
        self.review_id = review[0]['reviewId']['reviewId']

        branch_in_review = self.get_branch()
        if 'branch' in branch_in_review:
            branch_in_review = branch_in_review['branch'][0]['name']                
        else: 
            branch_in_review = 'master'
        
        branch_in_review_re = ''.join(branch_in_review)
        exclude_versions = re.search(r'^\d\d\.(\d\d$|\d$)', branch_in_review_re)
        if exclude_versions is None:
            current_day = str((datetime.now()).strftime('%m/%d/%Y %H:%M'))
            current_day_datetime = datetime.strptime(current_day, '%m/%d/%Y %H:%M')
            previous_time = str((current_day_datetime - timedelta(minutes=15)).strftime('%m/%d/%Y %H:%M'))
            if previous_time >= update_date:
                self.close_or_reopen_review(False)
                self.add_review_label('ready', 'ready for review')

                if branch_in_review != 'master':
                    self.start_branch_tracking(branch_in_review)

                self.log.info('Review' + str(self.review_id) + ' reopened')

            else:
                if 'labels' in review:
                    review_labels = review[0]['labels']

                    for label in review_labels:
                        self.delete_review_label(label['id'], label['name'])

                if branch_in_review != 'master':
                    self.stop_branch_tracking(branch_in_review)
                    self.update_status('Ready for Merge')

                else:
                    self.update_status('Ready for Test')

    #Return branch for issue
    def get_branch(self):
        url = self.url_upsource + '~rpc/getBranches'
        data = {"projectId":self.project_upsource, "limit":100, "query":self.issue_title}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        readble_json = answer.json()
        return readble_json['result']

    #Create review
    def create_review(self, revision_list):
        for revision in revision_list:
            if 'revisionCommitMessage' in revision:
                revision_title = revision['revisionCommitMessage']

                if 'Merge ' not in revision_title:
                    revision_id = revision['revisionId']
                    break

        url = self.url_upsource + '~rpc/createReview'
        data = {"projectId":self.project_upsource, "revisions":revision_id}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

        created_review = self.get_reviews(self.issue_title)
        self.review_id = created_review[0]['reviewId']['reviewId']

        url = self.url_upsource + '~rpc/renameReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "text":str(self.issue_title) + ' ' + str(self.issue_summary)}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

        self.add_review_label('ready', 'ready for review')
        self.delete_default_reviewer()
        self.add_url_to_issue()

        self.log.info('Review for ' + str(self.issue_title) + ' created')

    #Removes a default reviewer from a review
    def delete_default_reviewer(self):
        url = self.url_upsource + '~rpc/removeParticipantFromReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "participant":{"userId":"653c3d2e-394f-4c6b-8757-3e070c78c910", "role":2}}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Adds a review url to a issue
    def add_url_to_issue(self):
        self.issue_list_request.update(
            trackorId=self.issue_id,
            fields={'I_CODE_REVIEW':self.url_upsource + self.project_upsource + '/review/' + self.review_id}
            )

    #Returns review data
    def get_reviews(self, query):
        url = self.url_upsource + '~rpc/getReviews'
        data = {"projectId":self.project_upsource, "limit":100, "query":query}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        readble_json = answer.json()
        review = readble_json
        if 'reviews' in readble_json['result']:
            review = review['result']['reviews']
            return review
        else:
            return review

    #Change a review to a review for a branch
    def start_branch_tracking(self, branch):
        url = self.url_upsource + '~rpc/startBranchTracking'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "branch":branch}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Adds a label to a review
    def add_review_label(self, label_id, label_name):
        url = self.url_upsource + '~rpc/addReviewLabel'
        data = {"projectId":self.project_upsource, "reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "label":{"id":label_id, "name":label_name}}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Delete a label to a review
    def delete_review_label(self, label_id, label_name):
        url = self.url_upsource + '~rpc/removeReviewLabel'
        data = {"projectId":self.project_upsource, "reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "label":{"id":label_id, "name":label_name}}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Close or reopen review
    def close_or_reopen_review(self, status):
        url = self.url_upsource + '~rpc/closeReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "isFlagged":status}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Updates issue status
    def update_status(self, status):
        self.issue_list_request.update(
            trackorId=self.issue_id,
            fields={'VQS_IT_STATUS':status}
            )

        self.log.info('Issue ' + str(self.issue_title) + ' updated status to ' + str(status))

    #Stops branch tracking for a given review
    def stop_branch_tracking(self, branch):
        url = self.url_upsource + '~rpc/stopBranchTracking'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "branch":branch}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    def check_open_reviews(self):
        review_list = self.get_reviews('state: open')
        upsource_users = self.get_upsource_users()
        for review_data in review_list:
            self.review_id = review_data['reviewId']['reviewId']

            review_title = review_data['title']
            if 'Review of ' in review_title:
                start = review_title.find('Review of ')
                finish = review_title.find('-')
                self.issue_title = review_title[start+10:finish+7]
            else:
                self.issue_title = review_title[review_title.find('') : review_title.find(' ')]

            issue = self.check_issue('')

            if len(issue) > 0:
                issue_status = issue[0]['VQS_IT_STATUS']

                if issue_status in ['Ready for Test', 'Ready for Merge', 'Closed']:
                    self.close_or_reopen_review(True)

                    if 'labels' in review_data:
                        review_labels = review_data['labels']
                        for label in review_labels:
                            self.delete_review_label(label['id'], label['name'])

                    branch_in_review = self.get_branch()
                    if 'branch' in branch_in_review:
                        branch_in_review = branch_in_review['branch'][0]['name']
                        self.stop_branch_tracking(branch_in_review)

                    self.log.info('Review ' + str(self.review_id) + ' closed')

                else:
                    self.issue_uat_date = issue[0]['Version.VER_UAT_DATE']
                    review_status = review_data['state']

                    if review_status == 1:            
                        self.setting_branch_tracking()
                        self.setting_participants(review_data, upsource_users)

                        if self.issue_uat_date != None:
                            self.setting_current_release_label()

                    if issue_status == 'In Progress':
                        self.add_review_label('WIP', 'work in progress')
                        self.delete_review_label('ready', 'ready for review')

                    elif issue_status == 'Ready for Review':
                        self.delete_review_label('WIP', 'work in progress')

    def get_upsource_users(self):
        reviewers_list = []
        for department in self.departments:
            department_reviewers = department['reviewers']
            department_fie_patterns = department['filePatterns']

            for reviewer in department_reviewers:
                try:
                    upsource_user = self.find_user_in_upsource(reviewer)
                except Exception as e:
                    self.log('Failed to find_user_in_upsource. Exception [%s]' % str(e))

                if 'infos' in upsource_user:
                    reviewer_id = upsource_user['infos'][0]['userId']
                    reviewers_list.append({'reviewer_id': reviewer_id, 'reviewer_name': reviewer,
                                           'reviewer_extension': department_fie_patterns})

        return reviewers_list

    def find_user_in_upsource(self, reviewer_name):
        url = self.url_upsource + '~rpc/findUsers'
        data = {'projectId': self.project_upsource, 'pattern': reviewer_name, 'limit': 100}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']
        else:
            raise Exception(answer.text)

    #Start branch tracking if review in a branch otherwise attaches revision to review
    def setting_branch_tracking(self):
        branch_in_review = self.get_branch()
        if 'branch' in branch_in_review:
            branch_in_review = branch_in_review['branch'][0]['name']
            branch_in_review_re = ''.join(branch_in_review)
            exclude_versions = re.search(r'^\d\d\.(\d\d$|\d$)', branch_in_review_re)
            if exclude_versions is None:
                self.start_branch_tracking(branch_in_review)

        else:
            self.add_revision_to_review()

    #Attaches revision to review
    def add_revision_to_review(self):
        revision_list = self.check_revision()

        if revision_list is not None and 'revision' in revision_list:
            revision_in_revision_list = revision_list['revision']
            for revision in revision_in_revision_list:
                revision_id = revision['revisionId']
                revision_title = revision['revisionCommitMessage']

                if 'Merge ' not in revision_title:
                    url = self.url_upsource + '~rpc/addRevisionToReview'
                    data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "revisionId":revision_id}
                    requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Added participants in review
    def setting_participants(self, review_data, upsource_users):
        if len(upsource_users) > 0:
            review_participants_list = []
            for review_participant in review_data['participants']:
                review_participants_list.append(review_participant['userId'])

            extension_list = self.get_review_file_extensions()
            for extension in extension_list:
                for user_data in upsource_users:
                    user_id = user_data['reviewer_id']
                    user_extension = user_data['reviewer_extension']
                    if extension in user_extension and user_id not in review_participants_list:
                        self.add_reviewer(user_id)
                        break

    def get_review_file_extensions(self):
        changed_files = self.get_review_summary_changes()
        extension_list = []
        for changed_file in changed_files:
            file_icon = changed_file['fileIcon']
            file_extension = file_icon[file_icon.rfind(':')+1:]

            if file_extension != '' and file_extension not in extension_list:
                extension_list.append(file_extension)

        return extension_list

    #Returns the code ownership summary for a given review
    def get_review_summary_changes(self):
        url = self.url_upsource + '~rpc/getReviewSummaryChanges'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "revisions":{"selectAll":True}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        changed_file = answer.json()['result']['diff']
        if 'diff' in changed_file:
            return changed_file['diff']
        else:
            return []

    #Add a reviewer to the review
    def add_reviewer(self, reviewer_id):
        url = self.url_upsource + '~rpc/addParticipantToReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "participant":{"userId":reviewer_id, "role":2}}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Checks release date and adds or removes label
    def setting_current_release_label(self):                        
        datetime_object = datetime.strptime(self.issue_uat_date, '%Y-%m-%d')
        current_release = str(datetime_object.strftime('%m/%d/%Y'))
        
        sysdate = str((datetime.now()).strftime('%m/%d/%Y'))
        next_two_week = str((datetime.now() + timedelta(days=13)).strftime('%m/%d/%Y'))

        if current_release >= sysdate and current_release <= next_two_week:
            self.add_review_label('1ce36262-9d48-4b0e-93bd-d93722776e45', 'current release')

        elif current_release < sysdate or current_release > next_two_week:
            self.delete_review_label('1ce36262-9d48-4b0e-93bd-d93722776e45', 'current release')

    #Removes labels from closed reviews and stop branch tracking
    def check_closed_reviews(self):
        labels_list = self.get_review_labels()

        label_names = ''
        for label in labels_list['predefinedLabels']:
            label_names = label_names + '{' + label['name'] + '}' + ','

        for label in labels_list['customLabels']:
            label_names = label_names + '{' + label['name'] + '}' + ','

        review_list = self.get_reviews('state:closed and (#track or label: ' + label_names[:-1] + ')')
        if isinstance(review_list, list) and len(review_list) > 0 and 'reviewId' in review_list[0]:
            for review_data in review_list:
                self.review_id = review_data['reviewId']['reviewId']

                if 'labels' in review_data:
                    review_labels = review_data['labels']
                    for label in review_labels:
                        self.delete_review_label(label['id'], label['name'])

                branch_in_review = self.get_branch()
                if 'branch' in branch_in_review:
                    branch_in_review = branch_in_review['branch'][0]['name'] 
                    self.stop_branch_tracking(branch_in_review)

    def get_review_labels(self):
        url = self.url_upsource + '~rpc/getReviewLabels'
        data = {"projectId":self.project_upsource}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        response = answer.json()
        readble_json = response['result']
        return readble_json

    def url_setting(self, url):
        url_re = re.search('upsource', url)
        url_re_start = re.search('^https', url)
        url_re_finish = re.search('/$', url)
        if url_re is None:
            if url_re_start is not None and url_re_finish is not None:
                url_split = re.split('://',url[:-1],2)
                url = url_split[1]  
            elif url_re_start is None and url_re_finish is not None:
                url = url[:-1]
            elif url_re_start is not None and url_re_finish is None:
                url_split = re.split('://',url,2)
                url = url_split[1]
        else:
            if url_re_start is None and url_re_finish is None:
                url = 'https://' + url + '/'
            elif url_re_start is None and url_re_finish is not None:
                url = 'https://' + url
            elif url_re_start is not None and url_re_finish is None:
                url = url + '/'

        return url

    #Returns logging to stdout
    def get_logger(self, name=__file__, file='log.txt', encoding='utf-8'):
        log = logging.getLogger(name)
        log.setLevel(logging.DEBUG)
        formatter = logging.Formatter('[%(asctime)s] %(filename)s:%(lineno)d %(levelname)-8s %(message)s')
        sh = logging.StreamHandler(stream=sys.stdout)
        sh.setFormatter(formatter)
        log.addHandler(sh)
        return log
