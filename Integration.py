from IntegrationLog import IntegrationLog
from UrlSetting import UrlSetting
from enum import Enum
from datetime import datetime, timedelta
import re


class Integration:
    def __init__(self, issue, review):
        self.issue = issue
        self.review = review
        self.log = IntegrationLog().get_logger()
        self.upsource_users = self.get_upsource_users()

    def start_integration(self):
        self.log.info('Starting integration')
        self.create_review_label()

        for issue in self.issue.get_issue_list_for_review():
            issue_id = issue['TRACKOR_ID']
            issue_title = issue['TRACKOR_KEY']
            issue_summary = issue['VQS_IT_XITOR_NAME']

            revision_list = self.review.filtered_revision_list(issue_title)
            if revision_list is not None and 'revision' in revision_list:
                review = self.review.get_reviews(issue_title)
                if isinstance(review, list) and len(review) > 0 and 'reviewId' in review[0]:
                    if review[0]['state'] == ReviewState.CLOSED.value:
                        self.change_issue_status(review, issue_id, issue_title)
                else:
                    self.create_review_for_issue(revision_list['revision'], issue_id, issue_title, issue_summary)

        self.labels_list = self.review.get_review_labels()
        self.check_open_reviews()
        self.check_closed_reviews()

        self.log.info('Integration has been completed')

    def create_review_label(self):
        self.labels_list = self.review.get_review_labels()
        label_names_list = self.get_labels_list()

        for review_scope in self.review.review_scopes:
            ready_for_review_label = review_scope['label']
            raised_concern_label = '!' + review_scope['label']
            if ready_for_review_label not in label_names_list:
                self.review.create_or_edit_review_label(ready_for_review_label, str(LabelColor.GREEN.value))
            if raised_concern_label not in label_names_list:
                self.review.create_or_edit_review_label(raised_concern_label, str(LabelColor.RED.value))

    def get_labels_list(self, status=''):
        label_names = ''
        label_names_list = []
        self.labels_list = self.review.get_review_labels()
        if self.labels_list is not None and 'predefinedLabels' in self.labels_list:
            for label in self.labels_list['predefinedLabels']:
                if status == 'closed':
                    label_names = label_names + '{' + label['name'] + '}' + ','
                elif status == 'open':
                    label_names_list.append({'label_id': label['id'], 'label_name': label['name']})
                else:
                    label_names_list.append(label['name'])

        if self.labels_list is not None and 'customLabels' in self.labels_list:
            for label in self.labels_list['customLabels']:
                if status == 'closed':
                    label_names = label_names + '{' + label['name'] + '}' + ','
                elif status == 'open':
                    label_names_list.append({'label_id': label['id'], 'label_name': label['name']})
                else:
                    label_names_list.append(label['name'])

        if len(label_names) > 0:
            return label_names
        else:
            return label_names_list

    def change_issue_status(self, review, issue_id, issue_title):
        review_updated_at = str(review[0]['updatedAt'])[:-3]
        update_date = str(datetime.fromtimestamp(int(review_updated_at)).strftime('%m/%d/%Y %H:%M'))
        review_id = review[0]['reviewId']['reviewId']

        branch = self.set_branch_tracking_for_review(issue_title, review_id)
        branch_re = ''.join(branch)
        exclude_versions = re.search(r'^\d\d\.(\d\d$|\d$)', branch_re)
        if exclude_versions is None:
            current_day = str((datetime.now()).strftime('%m/%d/%Y %H:%M'))
            current_day_datetime = datetime.strptime(current_day, '%m/%d/%Y %H:%M')
            previous_time = str((current_day_datetime - timedelta(minutes=15)).strftime('%m/%d/%Y %H:%M'))
            if previous_time >= update_date:
                try:
                    reopened_review = self.review.close_or_reopen_review(False, review_id)
                except Exception as e:
                    self.log.warning('Failed to close_or_reopen_review. Exception [%s]' % str(e))
                    reopened_review = None

                if reopened_review is not None:
                    self.log.debug('Review ' + str(review_id) + ' reopened for Issue ' + issue_title)
            else:
                if 'labels' in review:
                    for label in review[0]['labels']:
                        self.review.add_or_remove_review_label(review_id, label['id'], label['name'], 'remove')

                if branch == 'master':
                    self.issue.update_issue_status(issue_id, IssueState.TEST)
                    self.log.info('Issue ' + str(issue_title) + ' updated status to ' + IssueState.TEST)
                else:
                    self.issue.update_issue_status(issue_id, IssueState.MERGE)
                    self.log.info('Issue ' + str(issue_title) + ' updated status to ' + IssueState.MERGE)

    def set_branch_tracking_for_review(self, issue_title, review_id):
        try:
            branch_in_review = self.review.get_branch(issue_title)
        except Exception as e:
            self.log.warning('Failed to get_branch. Exception [%s]' % str(e))
            branch_in_review = None

        if branch_in_review is not None and 'branch' in branch_in_review:
            branch = branch_in_review['branch'][0]['name']
            if 'reviewId' in branch_in_review['branch'][0]:
                self.review.stop_branch_tracking(branch, review_id)
        else:
            branch = 'master'

        return branch

    def create_review_for_issue(self, revision_list, issue_id, issue_title, issue_summary):
        for revision in revision_list:
            if 'Merge' not in revision['revisionCommitMessage']:
                revision_id = revision['revisionId']
                break

        review = self.review.create_review(revision_id)
        if review is not None:
            created_review = self.review.get_reviews(issue_title)
            if isinstance(created_review, list) and len(created_review) > 0 and 'reviewId' in created_review[0]:
                review_id = created_review[0]['reviewId']['reviewId']
                self.issue.add_url_to_issue(issue_id, self.review.url_upsource, self.review.project_upsource, review_id)
                self.review.rename_review(review_id, issue_title, issue_summary)

                try:
                    upsource_user = self.review.find_user_in_upsource(self.review.user_name_upsource)
                except Exception as e:
                    self.log.warning('Failed to find_user_in_upsource. Exception [%s]' % str(e))
                    upsource_user = None

                if upsource_user is not None:
                    self.review.delete_default_reviewer(upsource_user['infos'][0]['userId'], review_id, ParticipantRole.REVIEWER.value)

                self.log.info('Review for ' + str(issue_title) + ' created')

    def check_open_reviews(self):
        review_list = self.review.get_reviews('state: open')
        if isinstance(review_list, list) and len(review_list) > 0 and 'reviewId' in review_list[0]:
            self.upsource_users = self.get_upsource_users()
            label_names_list = self.get_labels_list('open')

            for review_data in review_list:
                review_id = review_data['reviewId']['reviewId']
                issue_title = self.get_issue_title(review_data['title'])
                self.set_branch_tracking_for_review(issue_title, review_id)
                issue = self.issue.get_issue_list_by_title(issue_title)
                if len(issue) > 0:
                    issue_status = issue[0]['VQS_IT_STATUS']
                    issue_uat_date = issue[0]['Version.VER_UAT_DATE']
                    if issue_status in [IssueState.TEST, IssueState.MERGE, IssueState.CLOSED]:
                        try:
                            closed_review = self.review.close_or_reopen_review(True, review_id)
                        except Exception as e:
                            self.log.warning('Failed to close_or_reopen_review. Exception [%s]' % str(e))
                            closed_review = None

                        if closed_review is not None:
                            self.remove_labels_for_closed_review(review_data, review_id)
                            self.log.debug('Review ' + str(review_id) + ' closed for Issue ' + issue_title)
                    else:
                        if review_data['state'] == ReviewState.OPENED.value:
                            if len(self.upsource_users) > 0:
                                self.add_revision_to_review(review_data, review_id, issue_title)
                                self.add_reviewers(review_id)
                                self.set_labels_for_review(review_id, label_names_list, issue_uat_date, issue_status)

    def get_upsource_users(self):
        reviewers_list = []
        for review_scope in self.review.review_scopes:
            review_scope_reviewers = review_scope['reviewers']
            review_scope_file_patterns = review_scope['filePatterns']
            review_scope_label = review_scope['label']

            for reviewer in review_scope_reviewers:
                try:
                    upsource_user = self.review.find_user_in_upsource(reviewer['name'])
                except Exception as e:
                    self.log.warning('Failed to find_user_in_upsource. Exception [%s]' % str(e))
                    upsource_user = None

                if upsource_user is not None and 'infos' in upsource_user:
                    reviewer_id = upsource_user['infos'][0]['userId']
                    reviewers_list.append({'reviewer_id': reviewer_id, 'reviewer_name': reviewer, 'reviewer_token':reviewer['token'],
                                           'reviewer_extension': review_scope_file_patterns, 'reviewer_label':review_scope_label})

        return reviewers_list

    def get_issue_title(self, review_title):
        if 'Review of ' in review_title:
            start = review_title.find('Review of ')
            finish = review_title.find('-')
            issue_title = review_title[start+10:finish+7]
        else:
            issue_title = review_title[review_title.find('') : review_title.find(' ')]

        return issue_title

    def add_revision_to_review(self, review_data, review_id, issue_title):
        participants_before_add_list = []
        if 'participants' in review_data:
            participants_before_add_list = review_data['participants']

        revision_id_list = []
        revision_list = self.review.filtered_revision_list(issue_title)
        if revision_list is not None and 'revision' in revision_list:
            revision_in_revision_list = revision_list['revision']
            for revision in revision_in_revision_list:
                if 'Merge' not in revision['revisionCommitMessage']:
                    revision_id = revision['revisionId']
                    try:
                        revision_review_info = self.review.get_revision_in_review(revision_id)
                    except Exception as e:
                        self.log.warning('Failed to get_revision_in_review. Exception [%s]' % str(e))
                        revision_review_info = None

                    if revision_review_info is not None and len(revision_review_info) == 0:
                        revision_id_list.append(revision_id)
                        self.review.add_revision(revision_id, review_id)

        if len(revision_id_list) > 0 and len(participants_before_add_list) > 0:
            self.update_paricipant_status_for_review(participants_before_add_list, revision_id_list, review_id)

    def update_paricipant_status_for_review(self, paricipant_list, revision_id_list, review_id):
        file_list = self.get_review_file_extensions(review_id, revision_id_list)
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
                        self.review.update_participant_status(state, reviewer_token, review_id)
                    break

    def get_review_file_extensions(self, review_id, revision_id_list=''):
        extension_list = []
        changed_files = self.review.get_review_summary_changes(review_id, revision_id_list)
        for changed_file in changed_files:
            file_icon = changed_file['fileIcon']
            file_extension = file_icon[file_icon.rfind(':')+1:]

            if file_extension != '' and file_extension not in extension_list:
                extension_list.append(file_extension)

        return extension_list

    def add_reviewers(self, review_id):
        review_data = self.review.get_reviews(review_id)
        if isinstance(review_data, list) and len(review_data) > 0 and 'reviewId' in review_data[0]:
            review_participants_list = []
            if 'participants' in review_data[0]:
                for review_participant in review_data[0]['participants']:
                    review_participants_list.append(review_participant['userId'])

            extension_list = self.get_review_file_extensions(review_id)
            for extension in extension_list:
                for user_data in self.upsource_users:
                    user_id = user_data['reviewer_id']
                    user_extension = user_data['reviewer_extension']
                    if extension in user_extension and user_id not in review_participants_list:
                        self.review.add_reviewer(user_id, review_id)
                        break

    def set_labels_for_review(self, review_id, label_names_list, issue_uat_date, issue_status):
        review_data = self.review.get_reviews(review_id)
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
                    if reviewer_id == participant_id and participant_role == ParticipantRole.REVIEWER.value:
                        reviewer_participants_list.append({'user_state': state, 'reviewer_label': reviewer_label})
                        reviewer_participants_list.append({'user_state': state, 'reviewer_label': '!' + reviewer_label})

            for label in label_names_list:
                label_id = label['label_id']
                label_name = label['label_name']
                if label_name == 'current release' and issue_uat_date is not None:
                    self.set_current_release_label(review_id, issue_uat_date, label_id, label_name, review_labels_list)
                    continue
                if label_name == 'in progress':
                    if issue_status == IssueState.IN_PROGRESS:
                        if label_name not in review_labels_list:
                            self.review.add_or_remove_review_label(review_id, label_id, label_name, 'add')
                    else:
                        if label_name in review_labels_list:
                            self.review.add_or_remove_review_label(review_id, label_id, label_name, 'remove')
                    continue
                for reviewer in reviewer_participants_list:
                    user_state = reviewer['user_state']
                    reviewer_label = reviewer['reviewer_label']
                    if re.search(reviewer_label, label_name) is not None:
                        if user_state == ParticipantState.REJECTED.value:
                            if label_name not in review_labels_list and '!' in label_name:
                                self.review.add_or_remove_review_label(review_id, label_id, label_name, 'add')
                            if label_name in review_labels_list and '!' not in label_name:
                                self.review.add_or_remove_review_label(review_id,label_id, label_name, 'remove')
                        else:
                            if label_name in review_labels_list and '!' in label_name:
                                self.review.add_or_remove_review_label(review_id, label_id, label_name, 'remove')
                            if label_name not in review_labels_list and '!' not in label_name:
                                self.review.add_or_remove_review_label(review_id, label_id, label_name, 'add')
                        break

    def set_current_release_label(self, review_id, issue_uat_date, label_id, label_name, review_labels_list):
        datetime_object = datetime.strptime(issue_uat_date, '%Y-%m-%d')
        current_release = str(datetime_object.strftime('%m/%d/%Y'))
        sysdate = str((datetime.now()).strftime('%m/%d/%Y'))
        next_two_week = str((datetime.now() + timedelta(days=13)).strftime('%m/%d/%Y'))

        if current_release >= sysdate and current_release <= next_two_week and label_name not in review_labels_list:
            self.review.add_or_remove_review_label(review_id, label_id, label_name, 'add')

        elif current_release < sysdate or current_release > next_two_week and label_name in review_labels_list:
            self.review.add_or_remove_review_label(review_id, label_id, label_name, 'remove')

    def check_closed_reviews(self):
        label_names_list = self.get_labels_list('closed')
        review_list = self.review.get_reviews('state:closed and (#track or label: ' + label_names_list[:-1] + ')')
        if isinstance(review_list, list) and len(review_list) > 0 and 'reviewId' in review_list[0]:
            for review_data in review_list:
                review_id = review_data['reviewId']['reviewId']
                issue_title = self.get_issue_title(review_data['title'])
                self.set_branch_tracking_for_review(issue_title, review_id)
                self.remove_labels_for_closed_review(review_data, review_id)

    def remove_labels_for_closed_review(self, review_data, review_id):
        if 'labels' in review_data:
            review_labels = review_data['labels']
            for label in review_labels:
                self.review.add_or_remove_review_label(review_id, label['id'], label['name'], 'remove')


class IssueState:
    TEST = 'Ready for Test'
    MERGE = 'Ready for Merge'
    CLOSED = 'Closed'
    IN_PROGRESS = 'In Progress'


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


class ParticipantRole(Enum):
    REVIEWER = 2
