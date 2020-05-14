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

    def __init__(self, url_upsource="", user_name_upsource="", login_upsource="", pass_upsource="", project_upsource="", review_scopes="",
                 url_onevizion="", login_onevizion="", pass_onevizion="", product_onevizion="", trackor_type=""):
        self.url_upsource = self.url_setting(url_upsource)
        self.user_name_upsource = user_name_upsource
        self.project_upsource = project_upsource
        self.auth_upsource = HTTPBasicAuth(login_upsource, pass_upsource)
        self.review_scopes = review_scopes

        self.url_onevizion = self.url_setting(url_onevizion)
        self.product_onevizion = product_onevizion
        self.issue_list_request = onevizion.Trackor(trackorType=trackor_type, URL=self.url_onevizion, userName=login_onevizion, password=pass_onevizion)

        self.headers = {'Content-type':'application/json','Content-Encoding':'utf-8'}
        self.log = self.get_logger()

    def start_integration(self):
        self.log.info('Starting integration')
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
                    self.create_review_for_issue(revision_list['revision'])
        
        self.labels_list = self.check_review_labels()
        self.check_open_reviews()
        self.check_closed_reviews()

        self.log.info('Integration has been completed')

    def check_issue(self, status=''):
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
            self.log.warning('Failed to filtered_revision_list. Exception [%s]' % str(e))
            revision_list = None

        return revision_list

    # Returns the list of revisions that match the given search query
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

        branch = self.set_branch_tracking_for_review()
        branch_re = ''.join(branch)
        exclude_versions = re.search(r'^\d\d\.(\d\d$|\d$)', branch_re)
        if exclude_versions is None:
            current_day = str((datetime.now()).strftime('%m/%d/%Y %H:%M'))
            current_day_datetime = datetime.strptime(current_day, '%m/%d/%Y %H:%M')
            previous_time = str((current_day_datetime - timedelta(minutes=15)).strftime('%m/%d/%Y %H:%M'))
            if previous_time >= update_date:
                try:
                    reopened_review = self.close_or_reopen_review(False)
                except Exception as e:
                    self.log.warning('Failed to close_or_reopen_review. Exception [%s]' % str(e))
                    reopened_review = None

                if reopened_review is not None:
                    self.log.debug('Review' + str(self.review_id) + ' reopened for Issue ' + self.issue_title)
            else:
                if 'labels' in review:
                    for label in review[0]['labels']:
                        try:
                            self.add_or_remove_review_label(label['id'], label['name'], 'remove')
                        except Exception as e:
                            self.log.warning('Failed to add_or_remove_review_label. Exception [%s]' % str(e))

                if branch == 'master':
                    self.update_issue_status('Ready for Test')
                else:
                    self.update_issue_status('Ready for Merge')

    def get_branch(self):
        url = self.url_upsource + '~rpc/getBranches'
        data = {"projectId":self.project_upsource, "limit":100, "query":self.issue_title}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']
        else:
            raise Exception(answer.text)

    def create_review_for_issue(self, revision_list):
        for revision in revision_list:
            if 'Merge' not in revision['revisionCommitMessage']:
                revision_id = revision['revisionId']
                break

        try:
            review = self.create_review(revision_id)
        except Exception as e:
            self.log.warning('Failed to create_review. Exception [%s]' % str(e))
            review = None

        if review is not None:
            created_review = self.check_review(self.issue_title)
            if isinstance(created_review, list) and len(created_review) > 0 and 'reviewId' in created_review[0]:
                self.review_id = created_review[0]['reviewId']['reviewId']
                self.add_url_to_issue()
                try:
                    self.rename_review()
                except Exception as e:
                    self.log.warning('Failed to rename_review. Exception [%s]' % str(e))

                try:
                    upsource_user = self.find_user_in_upsource(self.user_name_upsource)
                except Exception as e:
                    self.log.warning('Failed to find_user_in_upsource. Exception [%s]' % str(e))
                    upsource_user = None

                if upsource_user is not None:
                    try:
                        self.delete_default_reviewer(upsource_user['infos'][0]['userId'])
                    except Exception as e:
                        self.log.warning('Failed to delete_default_reviewer. Exception [%s]' % str(e))

                self.log.info('Review for ' + str(self.issue_title) + ' created')

    def create_review(self, revision_id):
        url = self.url_upsource + '~rpc/createReview'
        data = {"projectId":self.project_upsource, "revisions":revision_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer
        else:
            raise Exception(answer.text)

    def rename_review(self):
        url = self.url_upsource + '~rpc/renameReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "text":str(self.issue_title) + ' ' + str(self.issue_summary)}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            raise Exception(answer.text)

    def delete_default_reviewer(self, user_id):
        url = self.url_upsource + '~rpc/removeParticipantFromReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, 
                "participant":{"userId":user_id, "role": Integration.ROLE_IN_REVIEW_REVIEWER}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            raise Exception(answer.text)

    def add_url_to_issue(self):
        self.issue_list_request.update(
            trackorId=self.issue_id,
            fields={'I_CODE_REVIEW':self.url_upsource + self.project_upsource + '/review/' + self.review_id}
            )

    def check_review(self, query):
        try:
            review = self.get_reviews(query)
        except Exception as e:
            self.log.warning('Failed to get_reviews. Exception [%s]' % str(e))
            review = None

        return review

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

    def add_or_remove_review_label(self, label_id, label_name, action):
        if action == 'add':
            url = self.url_upsource + '~rpc/addReviewLabel'
        if action == 'remove':
            url = self.url_upsource + '~rpc/removeReviewLabel'
        data = {"projectId":self.project_upsource, "reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, 
                "label":{"id":label_id, "name":label_name}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            raise Exception(answer.text)

    def close_or_reopen_review(self, status):
        url = self.url_upsource + '~rpc/closeReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "isFlagged":status}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer
        else:
            raise Exception(answer.text)

    def update_issue_status(self, status):
        self.issue_list_request.update(
            trackorId=self.issue_id,
            fields={'VQS_IT_STATUS':status}
            )

        self.log.info('Issue ' + str(self.issue_title) + ' updated status to ' + str(status))

    def stop_branch_tracking(self, branch):
        url = self.url_upsource + '~rpc/stopBranchTracking'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "branch":branch}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            raise Exception(answer.text)

    def check_open_reviews(self):
        review_list = self.check_review('state: open')
        if isinstance(review_list, list) and len(review_list) > 0 and 'reviewId' in review_list[0]:
            self.upsource_users = self.get_upsource_users()
            label_names_list = self.get_labels_list('open')

            for review_data in review_list:
                self.review_id = review_data['reviewId']['reviewId']
                self.issue_title = self.get_issue_title(review_data['title'])
                self.set_branch_tracking_for_review()
                issue = self.check_issue()
                if len(issue) > 0:
                    issue_status = issue[0]['VQS_IT_STATUS']
                    issue_uat_date = issue[0]['Version.VER_UAT_DATE']
                    if issue_status in ['Ready for Test', 'Ready for Merge', 'Closed']:
                        try:
                            closed_review = self.close_or_reopen_review(True)
                        except Exception as e:
                            self.log.warning('Failed to close_or_reopen_review. Exception [%s]' % str(e))
                            closed_review = None

                        if closed_review is not None:
                            self.remove_labels_for_closed_review(review_data)
                            self.log.debug('Review ' + str(self.review_id) + ' closed for Issue ' + self.issue_title)
                    else:
                        if review_data['state'] == ReviewState.OPENED.value:
                            if len(self.upsource_users) > 0:
                                self.add_revision_to_review(review_data)
                                self.add_reviewers()
                                self.set_labels_for_review(label_names_list, issue_uat_date, issue_status)

    def get_upsource_users(self):
        reviewers_list = []
        for review_scope in self.review_scopes:
            review_scope_reviewers = review_scope['reviewers']
            review_scope_file_patterns = review_scope['filePatterns']
            review_scope_label = review_scope['label']

            for reviewer in review_scope_reviewers:
                try:
                    upsource_user = self.find_user_in_upsource(reviewer['name'])
                except Exception as e:
                    self.log.warning('Failed to find_user_in_upsource. Exception [%s]' % str(e))
                    upsource_user = None

                if upsource_user is not None and 'infos' in upsource_user:
                    reviewer_id = upsource_user['infos'][0]['userId']
                    reviewers_list.append({'reviewer_id': reviewer_id, 'reviewer_name': reviewer['name'],
                                           'reviewer_extension': review_scope_file_patterns, 'reviewer_label':review_scope_label,
                                           'reviewer_token': reviewer['token']})

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

    def set_branch_tracking_for_review(self):
        try:
            branch_in_review = self.get_branch()
        except Exception as e:
            self.log.warning('Failed to get_branch. Exception [%s]' % str(e))
            branch_in_review = None

        if branch_in_review is not None and 'branch' in branch_in_review:
            branch = branch_in_review['branch'][0]['name']
            if 'reviewId' in branch_in_review['branch'][0]:
                try:
                    self.stop_branch_tracking(branch)
                except Exception as e:
                    self.log.warning('Failed to stop_branch_tracking. Exception [%s]' % str(e))
        else:
            branch = 'master'

        return branch

    def add_revision_to_review(self, review_data):
        participants_before_add_list = []
        if 'participants' in review_data:
            participants_before_add_list = review_data['participants']

        revision_id_list = []
        revision_list = self.check_revision()
        if revision_list is not None and 'revision' in revision_list:
            revision_in_revision_list = revision_list['revision']
            for revision in revision_in_revision_list:
                if 'Merge' not in revision['revisionCommitMessage']:
                    revision_id = revision['revisionId']
                    try:
                        revision_review_info = self.get_revision_in_review(revision_id)
                    except Exception as e:
                        self.log.warning('Failed to get_revision_in_review. Exception [%s]' % str(e))
                        revision_review_info = None

                    if revision_review_info is not None and len(revision_review_info) == 0:
                        revision_id_list.append(revision_id)
                        try:
                            self.add_revision(revision_id)
                        except Exception as e:
                            self.log.warning('Failed to add_revision. Exception [%s]' % str(e))

        if len(revision_id_list) > 0 and len(participants_before_add_list) > 0:
            self.update_paricipant_status_for_review(participants_before_add_list, revision_id_list)

    def get_revision_in_review(self, revision_id):
        url = self.url_upsource + '~rpc/getRevisionReviewInfo'
        data = {"projectId": self.project_upsource, "revisionId": revision_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']['reviewInfo'][0]
        else:
            raise Exception(answer.text)

    def add_revision(self, revision_id):
        url = self.url_upsource + '~rpc/addRevisionToReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id},
                "revisionId":revision_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            raise Exception(answer.text)

    def update_paricipant_status_for_review(self, paricipant_list, revision_id_list):
        file_list = self.get_review_file_extensions(revision_id_list)
        for participant in paricipant_list:
            state = participant['state']
            user_id = participant['userId']
            for user_data in self.upsource_users:
                reviewer_id = user_data['reviewer_id']
                reviewer_token = user_data['reviewer_token']
                reviewer_extension = user_data['reviewer_extension']
                if user_id == reviewer_id and state in (ParticipantState.ACCEPTED.value, ParticipantState.REJECTED.value):
                    file_extension_in_reviewer_extension = ''
                    for file_extension in file_list:
                        if file_extension in reviewer_extension:
                            file_extension_in_reviewer_extension = file_extension
                            break
                    if file_extension_in_reviewer_extension == '':
                        try:
                            self.update_participant_status(state, reviewer_token)
                        except Exception as e:
                            self.log.warning('Failed to update_participant_status. Exception [%s]' % str(e))
                    break

    def update_participant_status(self, state, reviewer_token):
        url = self.url_upsource + '~rpc/updateParticipantInReview'
        data = {"reviewId": {"projectId": self.project_upsource, "reviewId": self.review_id}, "state": state}
        headers_participant = {'Content-type': 'application/json', 'Content-Encoding': 'utf-8', 'Authorization': 'Bearer '}
        headers_participant['Authorization'] = 'Bearer ' + reviewer_token
        answer = requests.post(url, headers=headers_participant, data=json.dumps(data))
        if answer.ok == False:
            raise Exception(answer.text)

    def add_reviewers(self):
        review_data = self.check_review(self.review_id)
        if isinstance(review_data, list) and len(review_data) > 0 and 'reviewId' in review_data[0]:
            review_participants_list = []
            if 'participants' in review_data[0]:
                for review_participant in review_data[0]['participants']:
                    review_participants_list.append(review_participant['userId'])

            extension_list = self.get_review_file_extensions()
            for extension in extension_list:
                for user_data in self.upsource_users:
                    user_id = user_data['reviewer_id']
                    user_extension = user_data['reviewer_extension']
                    if extension in user_extension and user_id not in review_participants_list:
                        try:
                            self.add_reviewer(user_id)
                        except Exception as e:
                            self.log.warning('Failed to add_reviewer. Exception [%s]' % str(e))

                        break

    def get_review_file_extensions(self, revision_id_list=''):
        try:
            changed_files = self.get_review_summary_changes(revision_id_list)
        except Exception as e:
            self.log.warning('Failed to get_review_summary_changes. Exception [%s]' % str(e))
            changed_files = []

        extension_list = []
        for changed_file in changed_files:
            file_icon = changed_file['fileIcon']
            file_extension = file_icon[file_icon.rfind(':')+1:]

            if file_extension != '' and file_extension not in extension_list:
                extension_list.append(file_extension)

        return extension_list

    # Returns the code ownership summary for a given review
    def get_review_summary_changes(self, revision_id_list):
        url = self.url_upsource + '~rpc/getReviewSummaryChanges'
        if revision_id_list == '':
            data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "revisions":{"selectAll":True}}
        else:
            data = {"reviewId": {"projectId": self.project_upsource, "reviewId": self.review_id}, 
                    "revisions": {"revisions": revision_id_list}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            if 'diff' in answer.json()['result']['diff']:
                return answer.json()['result']['diff']['diff']
            else:
                return []
        else:
            raise Exception(answer.text)

    def add_reviewer(self, reviewer_id):
        url = self.url_upsource + '~rpc/addParticipantToReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":self.review_id}, "participant":{"userId":reviewer_id, "role":2}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            raise Exception(answer.text)

    def set_labels_for_review(self, label_names_list, issue_uat_date, issue_status):
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
                for user_data in self.upsource_users:
                    reviewer_id = user_data['reviewer_id']
                    reviewer_label = user_data['reviewer_label']
                    if reviewer_id == participant_id and participant_role == Integration.ROLE_IN_REVIEW_REVIEWER:
                        reviewer_participants_list.append({'user_state': state, 'reviewer_label': reviewer_label})
                        reviewer_participants_list.append({'user_state': state, 'reviewer_label': '!' + reviewer_label})

            for label in label_names_list:
                label_id = label['label_id']
                label_name = label['label_name']
                if label_name == 'current release' and issue_uat_date is not None:
                    self.set_current_release_label(issue_uat_date, label_id, label_name, review_labels_list)
                    continue
                if label_name == 'work in progress':
                    if issue_status == 'In Progress':
                        if label_name not in review_labels_list:
                            try:
                                self.add_or_remove_review_label(label_id, label_name, 'add')
                            except Exception as e:
                                self.log.warning('Failed to add_or_remove_review_label. Exception [%s]' % str(e))
                    else:
                        if label_name in review_labels_list:
                            try:
                                self.add_or_remove_review_label(label_id, label_name, 'remove')
                            except Exception as e:
                                self.log.warning('Failed to add_or_remove_review_label. Exception [%s]' % str(e))
                    continue
                for reviewer in reviewer_participants_list:
                    user_state = reviewer['user_state']
                    reviewer_label = reviewer['reviewer_label']
                    if re.search(reviewer_label, label_name) is not None:
                        if user_state == Integration.PARTICIPANT_STATE_REJECTED:
                            if label_name not in review_labels_list and '!' in label_name:
                                try:
                                    self.add_or_remove_review_label(label_id, label_name, 'add')
                                except Exception as e:
                                    self.log.warning('Failed to add_or_remove_review_label. Exception [%s]' % str(e))
                            if label_name in review_labels_list and '!' not in label_name:
                                try:
                                    self.add_or_remove_review_label(label_id, label_name, 'remove')
                                except Exception as e:
                                    self.log.warning('Failed to add_or_remove_review_label. Exception [%s]' % str(e))
                        else:
                            if label_name in review_labels_list and '!' in label_name:
                                try:
                                    self.add_or_remove_review_label(label_id, label_name, 'remove')
                                except Exception as e:
                                    self.log.warning('Failed to add_or_remove_review_label. Exception [%s]' % str(e))
                            if label_name not in review_labels_list and '!' not in label_name:
                                try:
                                    self.add_or_remove_review_label(label_id, label_name, 'add')
                                except Exception as e:
                                    self.log.warning('Failed to add_or_remove_review_label. Exception [%s]' % str(e))
                        break
    
    # Checks release date and adds or removes label
    def set_current_release_label(self, issue_uat_date, label_id, label_name, review_labels_list):
        datetime_object = datetime.strptime(issue_uat_date, '%Y-%m-%d')
        current_release = str(datetime_object.strftime('%m/%d/%Y'))
        sysdate = str((datetime.now()).strftime('%m/%d/%Y'))
        next_two_week = str((datetime.now() + timedelta(days=13)).strftime('%m/%d/%Y'))

        if current_release >= sysdate and current_release <= next_two_week and label_name not in review_labels_list:
            try:
                self.add_or_remove_review_label(label_id, label_name, 'add')
            except Exception as e:
                self.log.warning('Failed to add_or_remove_review_label. Exception [%s]' % str(e))

        elif current_release < sysdate or current_release > next_two_week and label_name in review_labels_list:
            try:
                self.add_or_remove_review_label(label_id, label_name, 'remove')
            except Exception as e:
                self.log.warning('Failed to add_or_remove_review_label. Exception [%s]' % str(e))

    # Removes labels from closed reviews and stop branch tracking
    def check_closed_reviews(self):
        label_names_list = self.get_labels_list('closed')
        label_names_str = str(label_names_list)
        label_names_str_re = re.split(r'\]', re.split(r'\[',label_names_str)[1])[0]
        review_list = self.check_review('state:closed and (#track or label: ' + label_names_str_re + ')')
        if isinstance(review_list, list) and len(review_list) > 0 and 'reviewId' in review_list[0]:
            for review_data in review_list:
                self.review_id = review_data['reviewId']['reviewId']
                self.set_branch_tracking_for_review()
                self.remove_labels_for_closed_review(review_data)

    def remove_labels_for_closed_review(self, review_data):
        if 'labels' in review_data:
            review_labels = review_data['labels']
            for label in review_labels:
                try:
                    self.add_or_remove_review_label(label['id'], label['name'], 'remove')
                except Exception as e:
                    self.log.warning('Failed to add_or_remove_review_label. Exception [%s]' % str(e))

    def get_labels_list(self, status=''):
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
        label_names_list = self.get_labels_list()

        for review_scope in self.review_scopes:
            ready_for_review_label = review_scope['label']
            raised_concern_label = '!' + review_scope['label']
            if ready_for_review_label not in label_names_list:
                try:
                    self.create_or_edit_review_label(ready_for_review_label, str(LabelColor.GREEN.value))
                except Exception as e:
                    self.log.warning('Failed to create_or_edit_review_label. Exception [%s]' % str(e))

            if raised_concern_label not in label_names_list:
                try:
                    self.create_or_edit_review_label(raised_concern_label, str(LabelColor.RED.value))
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

    # Returns logging to stdout
    def get_logger(self, name=__file__, file='log.txt', encoding='utf-8'):
        log = logging.getLogger(name)
        log.setLevel(logging.DEBUG)
        formatter = logging.Formatter('[%(asctime)s] %(filename)s:%(lineno)d %(levelname)-8s %(message)s')
        sh = logging.StreamHandler(stream=sys.stdout)
        sh.setFormatter(formatter)
        log.addHandler(sh)
        return log


class ReviewState(Enum):
    OPENED = 1
    CLOSED = 2


class LabelColor(Enum):
    GREEN = 0
    RED = 2


class ParticipantState(Enum):
    UNREAD = 1
    READ = 2
    ACCEPTED = 3
    REJECTED = 4
