from enum import Enum
import requests
from requests.auth import HTTPBasicAuth
import json
import logging
import sys
import re
import onevizion
from datetime import datetime, timedelta

class Integration(object):
    ROLE_IN_REVIEW_REVIEWER = 2
    PARTICIPANT_STATE_REJECTED = 4

    def __init__(self, url_upsource="", login_upsource="", pass_upsource="", project_upsource="", review_scopes="",
                 url_onevizion="", login_onevizion="", pass_onevizion="", product_onevizion="", trackor_type=""):
        self.url_upsource = self.url_setting(url_upsource)        
        self.project_upsource = project_upsource
        self.auth_upsource = HTTPBasicAuth(login_upsource, pass_upsource)
        self.review_scopes = review_scopes

        self.url_onevizion = self.url_setting(url_onevizion)
        self.product_onevizion = product_onevizion
        self.issue_list_request = onevizion.Trackor(trackorType=trackor_type, URL=self.url_onevizion, userName=login_onevizion, password=pass_onevizion)

        self.headers = {'Content-type':'application/json','Content-Encoding':'utf-8'}
        self.log = self.get_logger()

    def start_integration(self):
        self.log.info('Started upsource integration')
        self.create_review_label()

        issue_list = self.check_issue('Ready for Review')
        for issue in issue_list:
            self.issue_id = issue['TRACKOR_ID']
            self.issue_title = issue['TRACKOR_KEY']
            self.issue_summary = issue['VQS_IT_XITOR_NAME']

            revision_list = self.check_revision()
            if revision_list is not None and 'revision' in revision_list:
                review = self.check_review(self.issue_title)
                if isinstance(review, list) and len(review) > 0 and 'reviewId' in review[0]:
                    if review[0]['state'] == ReviewState.CLOSED.value:
                        self.change_issue_status(review)
                else:
                    self.create_review(revision_list['revision'])
        
        self.labels_list = self.check_review_labels()
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
        return self.issue_list_request.jsonData

    def check_revision(self):
        try:
            revision_list = self.filtered_revision_list()
        except Exception as e:
            self.log.warning('Failed to check_review. Exception [%s]' % str(e))
            revision_list = None

        return revision_list

    #Returns the list of revisions that match the given search query
    def filtered_revision_list(self):
        url = self.url_upsource + '~rpc/getRevisionsListFiltered'
        data = {"projectId":self.project_upsource, "limit":100, "query":self.issue_title}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']
        else:
            raise Exception(answer.text)

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

                if branch_in_review != 'master':
                    self.start_branch_tracking(branch_in_review)

                self.log.info('Review' + str(self.review_id) + ' reopened for Issue ' + self.issue_title)
            else:
                if 'labels' in review:
                    for label in review[0]['labels']:
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

        created_review = self.check_review(self.issue_title)
        if isinstance(created_review, list) and len(created_review) > 0 and 'reviewId' in created_review[0]:
            self.review_id = created_review[0]['reviewId']['reviewId']

            url = self.url_upsource + '~rpc/renameReview'
            data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "text":str(self.issue_title) + ' ' + str(self.issue_summary)}
            requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

            self.delete_default_reviewer()
            self.add_url_to_issue()

            self.log.info('Review for ' + str(self.issue_title) + ' created')

    #Removes a default reviewer from a review
    def delete_default_reviewer(self):
        url = self.url_upsource + '~rpc/removeParticipantFromReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "participant":{"userId":"653c3d2e-394f-4c6b-8757-3e070c78c910", "role": Integration.ROLE_IN_REVIEW_REVIEWER}}
        requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)

    #Adds a review url to a issue
    def add_url_to_issue(self):
        self.issue_list_request.update(
            trackorId=self.issue_id,
            fields={'I_CODE_REVIEW':self.url_upsource + self.project_upsource + '/review/' + self.review_id}
            )

    def check_review(self, query):
        try:
            review = self.get_reviews(query)
        except Exception as e:
            self.log.warning('Failed to check_review. Exception [%s]' % str(e))
            review = None

        return review

    #Returns review data
    def get_reviews(self, query):
        url = self.url_upsource + '~rpc/getReviews'
        data = {"projectId":self.project_upsource, "limit":100, "query":query}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            if 'reviews' in answer.json()['result']:
                return answer.json()['result']['reviews']
            else:
                return answer.json()
        else:
            raise Exception(answer.text)

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
        review_list = self.check_review('state: open')
        if isinstance(review_list, list) and len(review_list) > 0 and 'reviewId' in review_list[0]:
            upsource_users = self.get_upsource_users()
            label_names_list = self.get_labels_list('open')

            for review_data in review_list:
                self.review_id = review_data['reviewId']['reviewId']
                self.issue_title = self.get_issue_title(review_data['title'])
                issue = self.check_issue('')
                if len(issue) > 0:
                    issue_status = issue[0]['VQS_IT_STATUS']
                    issue_uat_date = issue[0]['Version.VER_UAT_DATE']
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
                        if review_data['state'] == ReviewState.OPEN.value:            
                            self.setting_branch_tracking()
                            if len(upsource_users) > 0:
                                self.setting_participants(upsource_users)
                                self.set_labels_for_review(label_names_list, issue_uat_date, issue_status, upsource_users)

    def get_upsource_users(self):
        reviewers_list = []
        for review_scope in self.review_scopes:
            review_scope_reviewers = review_scope['reviewers']
            review_scope_file_patterns = review_scope['filePatterns']
            review_scope_label = review_scope['label']

            for reviewer in review_scope_reviewers:
                try:
                    upsource_user = self.find_user_in_upsource(reviewer)
                except Exception as e:
                    self.log.warning('Failed to find_user_in_upsource. Exception [%s]' % str(e))
                    upsource_user = None

                if upsource_user is not None and 'infos' in upsource_user:
                    reviewer_id = upsource_user['infos'][0]['userId']
                    reviewers_list.append({'reviewer_id': reviewer_id, 'reviewer_name': reviewer,
                                           'reviewer_extension': review_scope_file_patterns, 'reviewer_label':review_scope_label})

        return reviewers_list

    def find_user_in_upsource(self, reviewer_name):
        url = self.url_upsource + '~rpc/findUsers'
        data = {'projectId': self.project_upsource, 'pattern': reviewer_name, 'limit': 100}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']
        else:
            raise Exception(answer.text)

    def get_issue_title(self, review_title):
        if 'Review of ' in review_title:
            start = review_title.find('Review of ')
            finish = review_title.find('-')
            issue_title = review_title[start+10:finish+7]
        else:
            issue_title = review_title[review_title.find('') : review_title.find(' ')]

        return issue_title

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
    def setting_participants(self, upsource_users):
        review_data = self.check_review(self.review_id)
        if isinstance(review_data, list) and len(review_data) > 0 and 'reviewId' in review_data[0]:
            review_participants_list = []
            if 'participants' in review_data[0]:
                for review_participant in review_data[0]['participants']:
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

    def set_labels_for_review(self, label_names_list, issue_uat_date, issue_status, upsource_users):
        review_data = self.check_review(self.review_id)
        if isinstance(review_data, list) and len(review_data) > 0 and 'reviewId' in review_data[0]:
            review_participants = []
            if 'participants' in review_data[0]:
                review_participants = review_data[0]['participants']

            review_labels_list = []
            if 'labels' in review_data[0]:
                review_labels = review_data[0]['labels']
                for label in review_labels:
                    review_labels_list.append(label['name'])

            reviewer_participants_list = []
            for participant in review_participants:
                participant_id = participant['userId']
                participant_role = participant['role']
                state = participant['state']
                for user_data in upsource_users:
                    reviewer_id = user_data['reviewer_id']
                    reviewer_label = user_data['reviewer_label']
                    if reviewer_id == participant_id and participant_role == Integration.ROLE_IN_REVIEW_REVIEWER:
                        reviewer_participants_list.append({'user_state': state, 'reviewer_label': reviewer_label})
                        reviewer_participants_list.append({'user_state': state, 'reviewer_label': '!' + reviewer_label})

            for label in label_names_list:
                label_id = label['label_id']
                label_name = label['label_name']
                if label_name == 'current release' and issue_uat_date != None:
                    self.setting_current_release_label(issue_uat_date, label_id, label_name, review_labels_list)
                    continue
                if label_name == 'work in progress':
                    if issue_status == 'In Progress':
                        if label_name not in review_labels_list:
                            self.add_review_label(label_id, label_name)
                    else:
                        if label_name in review_labels_list:
                            self.delete_review_label(label_id, label_name)
                    continue
                for reviewer in reviewer_participants_list:
                    user_state = reviewer['user_state']
                    reviewer_label = reviewer['reviewer_label']
                    if re.search(reviewer_label, label_name) is not None:
                        if user_state == Integration.PARTICIPANT_STATE_REJECTED:
                            if label_name not in review_labels_list and '!' in label_name:
                                self.add_review_label(label_id, label_name)
                            if label_name in review_labels_list and '!' not in label_name:
                                self.delete_review_label(label_id, label_name)
                        else:
                            if label_name in review_labels_list and '!' in label_name:
                                self.delete_review_label(label_id, label_name)
                            if label_name not in review_labels_list and '!' not in label_name:
                                self.add_review_label(label_id, label_name)
                        break
    
    #Checks release date and adds or removes label
    def setting_current_release_label(self, issue_uat_date, label_id, label_name, review_labels_list):
        datetime_object = datetime.strptime(issue_uat_date, '%Y-%m-%d')
        current_release = str(datetime_object.strftime('%m/%d/%Y'))
        sysdate = str((datetime.now()).strftime('%m/%d/%Y'))
        next_two_week = str((datetime.now() + timedelta(days=13)).strftime('%m/%d/%Y'))

        if current_release >= sysdate and current_release <= next_two_week and label_name not in review_labels_list:
            self.add_review_label(label_id, label_name)

        elif current_release < sysdate or current_release > next_two_week and label_name in review_labels_list:
            self.delete_review_label(label_id, label_name)

    #Removes labels from closed reviews and stop branch tracking
    def check_closed_reviews(self):
        label_names_list = self.get_labels_list('closed')
        label_names_str = str(label_names_list)
        label_names_str_re = re.split(r'\]', re.split(r'\[',label_names_str)[1])[0]
        review_list = self.check_review('state:closed and (#track or label: ' + label_names_str_re + ')')
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

    def get_labels_list(self, status):
        label_names_list = []
        if self.labels_list is not None and 'predefinedLabels' in self.labels_list:
            for label in self.labels_list['predefinedLabels']:
                if status == 'closed':
                    label_names_list.append({label['name']})
                elif status == 'open':
                    label_names_list.append({'label_id': label['id'], 'label_name': label['name']})
                else:
                    label_names_list.append(label['name'])

        if self.labels_list is not None and 'customLabels' in self.labels_list:
            for label in self.labels_list['customLabels']:
                if status == 'closed':
                    label_names_list.append({label['name']})
                elif status == 'open':
                    label_names_list.append({'label_id': label['id'], 'label_name': label['name']})
                else:
                    label_names_list.append(label['name'])

        return label_names_list

    def create_review_label(self):
        self.labels_list = self.check_review_labels()
        label_names_list = self.get_labels_list('')

        for review_scope in self.review_scopes:
            ready_for_review_label = review_scope['label']
            raised_concern_label = '!' + review_scope['label']
            if ready_for_review_label not in label_names_list:
                try:
                    self.create_or_edit_review_label(ready_for_review_label, LabelColor.GREEN.value)
                except Exception as e:
                    self.log.warning('Failed to create_or_edit_review_label. Exception [%s]' % str(e))

            if raised_concern_label not in label_names_list:
                try:
                    self.create_or_edit_review_label(ready_for_review_label, LabelColor.RED.value)
                except Exception as e:
                    self.log.warning('Failed to create_or_edit_review_label. Exception [%s]' % str(e))

    def check_review_labels(self):
        try:
            review_labels = self.get_review_labels()
        except Exception as e:
            self.log.warning('Failed to get_review_labels. Exception [%s]' % str(e))
            review_labels = None

        return review_labels

    def get_review_labels(self):
        url = self.url_upsource + '~rpc/getReviewLabels'
        data = {"projectId":self.project_upsource}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']
        else:
            raise Exception(answer.text)

    def create_or_edit_review_label(self, label_name, label_color):
        url = self.url_upsource + '~rpc/createOrEditReviewLabel'
        data = {'projectId': self.project_upsource, 
                'label': {'id': label_name, 'name': label_name, 'colorId': label_color}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            raise Exception(answer.text)

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


class ReviewState(Enum):
    OPEN = 1
    CLOSED = 2


class LabelColor(Enum):
    GREEN = 0
    RED = 2
