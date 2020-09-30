import json
import re
from datetime import datetime, timedelta
from enum import Enum

import onevizion
import requests
from requests.auth import HTTPBasicAuth


class Integration:

    def __init__(self, issue, issue_task, review, logger):
        self.issue = issue
        self.issue_task = issue_task
        self.review = review
        self.log = logger
        self.reviewers = self.get_reviewers()

    def start_integration(self):
        self.log.info('Starting integration')

        for issue in self.issue.get_list_for_review():
            issue_id = issue[self.issue.issue_fields.ID]
            issue_title = issue[self.issue.issue_fields.TITLE]
            issue_summary = issue[self.issue.issue_fields.SUMMARY]

            review = self.review.get_list_on_query(issue_title)
            if review is None or (isinstance(review, list) and len(review) > 0 and 'reviewId' in review[0]):
                continue
            else:
                self.create_review_for_issue(issue_id, issue_title, issue_summary)

        self.check_open_reviews()

        self.log.info('Integration has been completed')

    def get_reviewers(self):
        reviewers_list = []
        for reviewer in self.review.reviewers:
            try:
                upsource_user = self.review.find_user_in_upsource(reviewer['name'])
            except Exception as e:
                self.log.warning('Failed to find_user_in_upsource. Exception [%s]' % str(e))
                upsource_user = None

            if upsource_user is not None and 'infos' in upsource_user:
                reviewer_id = upsource_user['infos'][0]['userId']
                reviewers_list.append(
                    {'reviewer_id': reviewer_id, 'reviewer_ov_name': reviewer['ovName']})

        return reviewers_list

    def create_review_for_issue(self, issue_id, issue_title, issue_summary):
        revision_id = None
        skip_revision_data = 0
        has_more_revisions = True
        while has_more_revisions:
            has_more_revisions = False
            revision_list = self.review.get_filtered_revision_list(issue_title, skip_revision_data)

            if revision_list is not None and 'revision' in revision_list:
                revision_in_revision_list = revision_list['revision']
                for revision in revision_in_revision_list:
                    if re.search('^Merge', revision['revisionCommitMessage']) is None:
                        revision_id = revision['revisionId']
                        break

                if revision_id == None and len(revision_in_revision_list) == self.review.LIMIT:
                    skip_revision_data += self.review.LIMIT
                    has_more_revisions = True

        if revision_id is None:
            self.log.warning('Failed to received revision_id for Issue ' + str(issue_title) + '. Review not created')
            return None

        review = self.review.create(revision_id)
        if review is not None:
            created_review = self.review.get_list_on_query(issue_title)
            if isinstance(created_review, list) and len(created_review) > 0 and 'reviewId' in created_review[0]:
                review_id = created_review[0]['reviewId']['reviewId']
                self.issue.update_code_review_url(issue_id, self.review.get_review_url(review_id))
                self.review.rename(review_id, issue_title, issue_summary)
                self.set_branch_tracking_for_review(issue_title, review_id)

                try:
                    upsource_user = self.review.find_user_in_upsource(self.review.user_name_upsource)
                except Exception as e:
                    self.log.warning('Failed to find_user_in_upsource. Exception [%s]' % str(e))
                    upsource_user = None

                if upsource_user is not None:
                    self.review.delete_default_reviewer(upsource_user['infos'][0]['userId'], review_id,
                                                        ParticipantRole.REVIEWER.value)

                self.log.info('Review for ' + str(issue_title) + ' created')

    def set_branch_tracking_for_review(self, issue_title, review_id):
        try:
            branch_in_review = self.review.get_branch(issue_title)
        except Exception as e:
            self.log.warning('Failed to get_branch. Exception [%s]' % str(e))
            branch_in_review = None

        if branch_in_review is not None and 'branch' in branch_in_review:
            branch = branch_in_review['branch'][0]['name']
            self.review.start_branch_tracking(branch, review_id)

    def check_open_reviews(self):
        review_list = self.review.get_list_on_query('state: open')
        if isinstance(review_list, list) and len(review_list) > 0 and 'reviewId' in review_list[0]:
            for review_data in review_list:
                review_id = review_data['reviewId']['reviewId']
                issue_title = self.get_issue_title(review_data['title'])
                if issue_title is None:
                    self.log.warning('Failed to get_issue_title from review ' + review_id)
                    continue

                issue = self.issue.get_list_by_title(issue_title)
                if len(issue) > 0:
                    issue_status = issue[0][self.issue.issue_fields.STATUS]
                    if issue_status in self.issue.issue_statuses.get_statuses_after_review():
                        try:
                            closed_review = self.review.close(True, review_id)
                        except Exception as e:
                            self.log.warning('Failed to close review. Exception [%s]' % str(e))
                            closed_review = None

                        if closed_review is not None:
                            self.log.debug('Review ' + str(review_id) + ' closed for Issue ' + issue_title)

                    else:
                        issue_tasks = self.issue_task.find_issue_tasks(issue_title)
                        self.add_task_urls_to_description(review_data, review_id, issue_tasks)
                        self.add_and_delete_reviewers(review_data, review_id, issue_tasks)
                        self.update_participant_status_for_review(review_id, issue_title)

    def get_issue_title(self, review_title):
        issue_title = re.search(Pattern.ISSUE_ID_PATTERN.value, review_title)
        if issue_title is not None:
            return issue_title.group()
        else:
            return None

    def add_task_urls_to_description(self, review_data, review_id, issue_tasks):
        review_description = ''
        if 'description' in review_data:
            review_description = review_data['description']

        new_review_description = review_description
        if len(new_review_description) == 0:
            for issue_task in issue_tasks:
                issue_task_key = issue_task['TRACKOR_KEY']
                issue_task_code_reviewer = issue_task['IT_CODE_REVIEWER']
                new_review_description = '[{0}](https://trackor.onevizion.com/trackor_types/Issue_Task/trackors.do?key={0}) {1}\n{2}'.format(issue_task_key, issue_task_code_reviewer, new_review_description)
        else:
            split_review_description = re.split('\n', new_review_description)
            for description_line in split_review_description:
                if re.search(Pattern.ISSUE_TASK_ID_PATTERN.value, description_line) is None:
                    break

                else:
                    is_issue_task_deleted = True
                    for issue_task in issue_tasks:
                        issue_task_key = issue_task['TRACKOR_KEY']
                        issue_task_code_reviewer = str(issue_task['IT_CODE_REVIEWER'])
                        if issue_task_key in description_line:

                            if issue_task_code_reviewer not in description_line:
                                new_code_reviewer_in_description = '[{0}](https://trackor.onevizion.com/trackor_types/Issue_Task/trackors.do?key={0}) {1}'.format(issue_task_key, issue_task_code_reviewer)
                                new_review_description = new_review_description.replace(description_line, new_code_reviewer_in_description)

                            is_issue_task_deleted = False
                            break

                    if is_issue_task_deleted:
                        if description_line + '\n' in new_review_description:
                            new_review_description = new_review_description.replace(description_line + '\n', '')
                        else:
                            new_review_description = new_review_description.replace(description_line, '')

            for issue_task in issue_tasks:
                issue_task_key = issue_task['TRACKOR_KEY']
                issue_task_code_reviewer = issue_task['IT_CODE_REVIEWER']
                if re.search(issue_task_key, new_review_description) is None:
                    new_review_description = '[{0}](https://trackor.onevizion.com/trackor_types/Issue_Task/trackors.do?key={0}) {1}\n{2}'.format(issue_task_key, issue_task_code_reviewer, new_review_description)

        if review_description != new_review_description:
            self.review.update_review_description(review_id, new_review_description)

    def add_and_delete_reviewers(self, review_data, review_id, issue_tasks):
        review_participants_list = []
        if 'participants' in review_data:
            for participant in review_data['participants']:
                if participant['role'] == ParticipantRole.REVIEWER.value:
                    is_reviewer_deleted = True
                    for reviewer in self.reviewers:
                        reviewer_id = reviewer['reviewer_id']
                        reviewer_ov_name = reviewer['reviewer_ov_name']

                        if reviewer_id == participant['userId']:
                            for issue_task in issue_tasks:
                                issue_task_code_reviewer = issue_task['IT_CODE_REVIEWER']
                                if reviewer_ov_name in issue_task_code_reviewer:
                                    is_reviewer_deleted = False
                                    break

                            if is_reviewer_deleted:
                                self.review.remove_reviewer(reviewer_id, review_id)
                            else:
                                review_participants_list.append(participant['userId'])
                            break

        for issue_task in issue_tasks:
            issue_task_code_reviewer = issue_task['IT_CODE_REVIEWER']
            for reviewer in self.reviewers:
                reviewer_id = reviewer['reviewer_id']
                reviewer_ov_name = reviewer['reviewer_ov_name']

                if reviewer_ov_name in issue_task_code_reviewer and reviewer_id not in review_participants_list:
                    self.review.add_reviewer(reviewer_id, review_id)
                    review_participants_list.append(reviewer_id)
                    break

    def update_participant_status_for_review(self, review_id, issue_title):
        review_data = self.review.get_list_on_query(review_id)
        if isinstance(review_data, list) and len(review_data) > 0 and 'reviewId' in review_data[0]:
            review_participants_list = []
            if 'participants' in review_data[0]:
                for participant in review_data[0]['participants']:
                    if participant['role'] == ParticipantRole.REVIEWER.value:
                        review_participants_list.append({'participant_id':participant['userId'], 'participant_state':participant['state']})

            for participant in review_participants_list:
                participant_id = participant['participant_id']
                participant_state = participant['participant_state']

                for reviewer in self.reviewers:
                    reviewer_id = reviewer['reviewer_id']
                    reviewer_ov_name = reviewer['reviewer_ov_name']

                    if participant_id == reviewer_id:
                        is_accepted = True
                        issue_tasks = self.issue_task.find_issue_tasks_for_reviewer(issue_title, reviewer_ov_name)
                        for issue_task in issue_tasks:
                            issue_task_status = issue_task['IT_STATUS']

                            if issue_task_status == self.issue_task.issue_task_statuses.AWAITING_RESPONSE:
                                if participant_state != ParticipantState.REJECTED.value:
                                    self.review.update_participant_status(ParticipantState.REJECTED.value, reviewer_id, review_id)
                                is_accepted = False
                                break

                            if issue_task_status != self.issue_task.issue_task_statuses.COMPLETED:
                                is_accepted = False
                                break

                        if is_accepted and participant_state != ParticipantState.ACCEPTED.value:
                            self.review.update_participant_status(ParticipantState.ACCEPTED.value, reviewer_id, review_id)

                        break


class Issue:
    def __init__(self, url_onevizion, login_onevizion, pass_onevizion, product_onevizion, issue_trackor_type,
                 issue_statuses, issue_fields):
        self.issue_statuses = IssueStatuses(issue_statuses)
        self.issue_fields = IssueFields(issue_fields)
        self.product_onevizion = product_onevizion
        self.issue_service = onevizion.Trackor(trackorType=issue_trackor_type, URL=url_onevizion,
                                               userName=login_onevizion, password=pass_onevizion)

    def get_list_for_review(self):
        self.issue_service.read(
            filters={self.issue_fields.PRODUCT: self.product_onevizion,
                     self.issue_fields.STATUS: self.issue_statuses.READY_FOR_REVIEW},
            fields=[self.issue_fields.TITLE, self.issue_fields.STATUS, self.issue_fields.SUMMARY]
        )

        return self.issue_service.jsonData

    def update_code_review_url(self, issue_id, code_review_url):
        self.issue_service.update(
            trackorId=issue_id,
            fields={self.issue_fields.CODE_REVIEW_URL: code_review_url}
        )

    def get_list_by_title(self, issue_title):
        self.issue_service.read(
            filters={self.issue_fields.PRODUCT: self.product_onevizion, self.issue_fields.TITLE: issue_title},
            fields=[self.issue_fields.TITLE, self.issue_fields.STATUS]
        )

        return self.issue_service.jsonData


class IssueTask:
    def __init__(self, url_onevizion, login_onevizion, pass_onevizion, issue_trackor_type,
                 issue_task_trackor_type, issue_fields, issue_task_fields, issue_task_types, issue_task_statuses):
        self.issue_fields = IssueFields(issue_fields)
        self.issue_task_fields = IssueTaskFields(issue_task_fields)
        self.issue_task_types = IssueTaskTypes(issue_task_types)
        self.issue_task_statuses = IssueTaskStatuses(issue_task_statuses)
        self.issue_trackor_type = issue_trackor_type
        self.issue_task_service = onevizion.Trackor(trackorType=issue_task_trackor_type, URL=url_onevizion,
                                                    userName=login_onevizion, password=pass_onevizion)

    def find_issue_tasks(self, issue_title):
        self.issue_task_service.read(
            filters={self.issue_task_fields.TYPE: self.issue_task_types.CODE_REVIEW_LABEL,
                     self.issue_task_fields.ISSUE: issue_title},
            fields=[self.issue_task_fields.REVIEWER, self.issue_task_fields.STATUS, self.issue_task_fields.TITLE])

        return self.issue_task_service.jsonData

    def find_issue_tasks_for_reviewer(self, issue_title, reviewer):
        self.issue_task_service.read(
            filters={self.issue_task_fields.TYPE: self.issue_task_types.CODE_REVIEW_LABEL,
                     self.issue_task_fields.ISSUE: issue_title,
                     self.issue_task_fields.REVIEWER: reviewer},
            fields=[self.issue_task_fields.STATUS])

        return self.issue_task_service.jsonData


class IssueStatuses:
    def __init__(self, issue_statuses):
        self.TEST = issue_statuses[IssueStatus.TEST.value]
        self.READY_FOR_MERGE = issue_statuses[IssueStatus.MERGE.value]
        self.CLOSED = issue_statuses[IssueStatus.CLOSED.value]
        self.COMPLETED = issue_statuses[IssueStatus.COMPLETED.value]
        self.CANCELED = issue_statuses[IssueStatus.CANCELED.value]
        self.READY_FOR_REVIEW = issue_statuses[IssueStatus.READY_FOR_REVIEW.value]

    def get_statuses_after_review(self):
        return [self.TEST, self.READY_FOR_MERGE, self.CLOSED, self.COMPLETED, self.CANCELED]


class IssueFields:
    def __init__(self, issue_fields):
        self.ID = issue_fields[IssueField.ID.value]
        self.TITLE = issue_fields[IssueField.TITLE.value]
        self.STATUS = issue_fields[IssueField.STATUS.value]
        self.SUMMARY = issue_fields[IssueField.SUMMARY.value]
        self.PRODUCT = issue_fields[IssueField.PRODUCT.value]
        self.CODE_REVIEW_URL = issue_fields[IssueField.CODE_REVIEW_URL.value]


class IssueTaskFields:
    def __init__(self, issue_task_fields):
        self.ID = issue_task_fields[IssueTaskField.ID.value]
        self.TITLE = issue_task_fields[IssueTaskField.TITLE.value]
        self.STATUS = issue_task_fields[IssueTaskField.STATUS.value]
        self.SUMMARY = issue_task_fields[IssueTaskField.SUMMARY.value]
        self.TYPE = issue_task_fields[IssueTaskField.TYPE.value]
        self.EST_HOURS = issue_task_fields[IssueTaskField.EST_HOURS.value]
        self.ASSIGNED_TO = issue_task_fields[IssueTaskField.ASSIGNED_TO.value]
        self.ISSUE = issue_task_fields[IssueTaskField.ISSUE.value]
        self.REVIEWER = issue_task_fields[IssueTaskField.REVIEWER.value]
        self.CODE_REVIEW_URL = issue_task_fields[IssueTaskField.CODE_REVIEW_URL.value]


class IssueTaskTypes:
    def __init__(self, issue_task_types):
        self.CODE_REVIEW = issue_task_types[IssueTaskType.CODE_REVIEW.value]
        self.CODE_REVIEW_LABEL = issue_task_types[IssueTaskType.CODE_REVIEW_LABEL.value]


class IssueTaskStatuses:
    def __init__(self, issue_task_statuses):
        self.COMPLETED = issue_task_statuses[IssueTaskStatus.COMPLETED.value]
        self.AWAITING_RESPONSE = issue_task_statuses[IssueTaskStatus.AWAITING_RESPONSE.value]


class Review:
    LIMIT = 100

    def __init__(self, url_upsource, user_name_upsource, login_upsource, pass_upsource, project_upsource, reviewers,
                 logger):
        self.url_upsource = url_upsource
        self.user_name_upsource = user_name_upsource
        self.project_upsource = project_upsource
        self.auth_upsource = HTTPBasicAuth(login_upsource, pass_upsource)
        self.reviewers = reviewers
        self.headers = {'Content-type': 'application/json', 'Content-Encoding': 'utf-8'}
        self.log = logger

    def get_filtered_revision_list(self, issue_title, skip_revision_data):
        url = self.url_upsource + '~rpc/getRevisionsListFiltered'
        data = {"projectId": self.project_upsource, "limit": Review.LIMIT, "skip":skip_revision_data, "query": issue_title}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']
        else:
            self.log.warning('Failed to filtered_revision_list. Exception [%s]' % str(answer.text))
            return None

    def close(self, status, review_id):
        url = self.url_upsource + '~rpc/closeReview'
        data = {"reviewId": {"projectId": self.project_upsource, "reviewId": review_id}, "isFlagged": status}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer
        else:
            raise Exception(answer.text)

    def get_branch(self, issue_title):
        url = self.url_upsource + '~rpc/getBranches'
        data = {"projectId": self.project_upsource, "limit": Review.LIMIT, "query": issue_title}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']
        else:
            raise Exception(answer.text)

    def start_branch_tracking(self, branch, review_id):
        url = self.url_upsource + '~rpc/startBranchTracking'
        data = {"reviewId": {"projectId": self.project_upsource, "reviewId": review_id}, "branch": branch}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to start_branch_tracking. Exception [%s]' % str(answer.text))

    def find_user_in_upsource(self, reviewer_name):
        url = self.url_upsource + '~rpc/findUsers'
        data = {'projectId': self.project_upsource, 'pattern': reviewer_name, 'limit': Review.LIMIT}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']
        else:
            raise Exception(answer.text)

    def update_participant_status(self, state, reviewer_id, review_id):
        url = self.url_upsource + '~rpc/updateParticipantInReview'
        data = {"reviewId": {"projectId": self.project_upsource, "reviewId": review_id}, "state": state, "userId":reviewer_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to update_participant_status. Exception [%s]' % str(answer.text))

    def add_reviewer(self, reviewer_id, review_id):
        url = self.url_upsource + '~rpc/addParticipantToReview'
        data = {"reviewId": {"projectId": self.project_upsource, "reviewId": review_id},
                "participant": {"userId": reviewer_id, "role": ParticipantRole.REVIEWER.value}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to add_reviewer. Exception [%s]' % str(answer.text))

    def remove_reviewer(self, reviewer_id, review_id):
        url = self.url_upsource + '~rpc/removeParticipantFromReview'
        data = {"reviewId": {"projectId": self.project_upsource, "reviewId": review_id},
                "participant": {"userId": reviewer_id, "role": ParticipantRole.REVIEWER.value}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to remove_reviewer. Exception [%s]' % str(answer.text))

    def get_list_on_query(self, query):
        url = self.url_upsource + '~rpc/getReviews'
        data = {"projectId": self.project_upsource, "limit": Review.LIMIT, "query": query}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            if 'reviews' in answer.json()['result']:
                return answer.json()['result']['reviews']
            else:
                return answer.json()
        else:
            self.log.warning('Failed to get_reviews. Exception [%s]' % str(answer.text))
            return None

    def delete_default_reviewer(self, user_id, review_id, role_in_review):
        url = self.url_upsource + '~rpc/removeParticipantFromReview'
        data = {"reviewId": {"projectId": self.project_upsource, "reviewId": review_id},
                "participant": {"userId": user_id, "role": role_in_review}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to delete_default_reviewer. Exception [%s]' % str(answer.text))

    def rename(self, review_id, issue_title, issue_summary):
        url = self.url_upsource + '~rpc/renameReview'
        data = {"reviewId": {"projectId": self.project_upsource, "reviewId": review_id},
                "text": str(issue_title) + ' ' + str(issue_summary)}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to rename_review. Exception [%s]' % str(answer.text))

    def create(self, revision_id):
        url = self.url_upsource + '~rpc/createReview'
        data = {"projectId": self.project_upsource, "revisions": revision_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer
        else:
            self.log.warning('Failed to create_review. Exception [%s]' % str(answer.text))
            return None

    def get_review_url(self, review_id):
        return self.url_upsource + self.project_upsource + '/review/' + review_id

    def update_review_description(self, review_id, description):
        url = self.url_upsource + '~rpc/editReviewDescription'
        data = {"reviewId": {"projectId": self.project_upsource, "reviewId": review_id},
                "text": description}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to update_review_description. Exception [%s]' % str(answer.text))


class IssueStatus(Enum):
    TEST = 'test'
    MERGE = 'readyForMerge'
    CLOSED = 'closed'
    COMPLETED = 'completed'
    CANCELED = 'canceled'
    READY_FOR_REVIEW = 'readyForReview'


class IssueTaskStatus(Enum):
    COMPLETED = 'completed'
    AWAITING_RESPONSE = 'awaitingResponse'


class IssueField(Enum):
    ID = 'id'
    TITLE = 'title'
    STATUS = 'status'
    SUMMARY = 'summary'
    PRODUCT = 'product'
    CODE_REVIEW_URL = 'codeReviewUrl'


class IssueTaskField(Enum):
    ID = 'id'
    TITLE = 'title'
    STATUS = 'status'
    SUMMARY = 'summary'
    TYPE = 'type'
    EST_HOURS = 'estHours'
    ASSIGNED_TO = 'assignedTo'
    ISSUE = 'issue'
    REVIEWER = 'reviewer'
    CODE_REVIEW_URL = 'codeReviewUrl'


class IssueTaskType(Enum):
    CODE_REVIEW = 'codeReview'
    CODE_REVIEW_LABEL = 'codeReviewLabel'


class ParticipantState(Enum):
    ACCEPTED = 3
    REJECTED = 4


class ParticipantRole(Enum):
    REVIEWER = 2


class Pattern(Enum):
    ISSUE_ID_PATTERN = r'\w+-\d+' # Example: Notif-163189
    ISSUE_TASK_ID_PATTERN = r'^\[\w+-\d+-\d+\]' # Example: Notif-163189-16732