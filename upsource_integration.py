from enum import Enum
import json
import re
import onevizion
import requests


class Integration:
    ISSUE_ID_PATTERN = r'\w+-\d+\s'  # Example: Notif-163189
    ISSUE_TASK_ID_PATTERN = r'\w+-\d+-\d+'  # Example: Notif-163189-16732
    ISSUE_TASK_ID_IN_URL_PATTERN = r'^\[\w+-\d+-\d+\]'  # Example: [Notif-163189-16732]

    def __init__(self, url_onevizion, products, issue, issue_task, review, logger):
        self.products = products
        self.issue = issue
        self.issue_task = issue_task
        self.review = review
        self.log = logger
        self.url_onevizion = url_onevizion
        self.issue_task_trackor_type = issue_task.issue_task_trackor_type

    def start_integration(self):
        self.log.info('Starting integration')

        for product in self.products:
            project_upsource = product['projectUpsource']
            product_onevizion = product['productOneVizion']

            self.log.info(f'Integrating {product_onevizion} product')

            self.reviewers = self.get_reviewers(project_upsource)
            self.upsource_user_id = self.review.get_upsource_user_id(project_upsource)

            self.integrate_product(product_onevizion, project_upsource)

        self.log.info('Integration has been completed')

    def get_reviewers(self, project_upsource):
        reviewers_list = []
        for reviewer in self.review.reviewers:
            try:
                upsource_user = self.review.find_user_in_upsource(reviewer['name'], project_upsource)
            except Exception as e:
                if re.search(f'{StatusCode.UNAUTHORIZED.value}|{StatusCode.EXCEPTION.value}', str(e)) is None:
                    upsource_user = None
                else:
                    raise Exception(f'Failed to get_reviewers - {reviewer["name"]}. Exception [{re.split("-", str(e))[1]}]')

            if upsource_user is not None and 'infos' in upsource_user:
                reviewer_id = upsource_user['infos'][0]['userId']
                reviewers_list.append(
                    {'reviewer_id': reviewer_id, 'reviewer_ov_name': reviewer['ovName']})

        return reviewers_list

    def integrate_product(self, product_onevizion, project_upsource):
        issue_list = self.issue.get_list_for_review(product_onevizion)
        if len(issue_list) == 0:
            self.log.info('No Code Review Issue found.')

        for issue in issue_list:
            issue_id = issue[self.issue.issue_fields.ID]
            issue_title = issue[self.issue.issue_fields.TITLE]
            issue_summary = issue[self.issue.issue_fields.SUMMARY]

            review = self.review.get_list_on_query(issue_title, project_upsource)
            if review is not None and isinstance(review, list) is False:
                revision_id = self.find_revision(issue_title, project_upsource)
                if revision_id is not None:
                    self.create_review(revision_id, issue_id, issue_title, issue_summary, project_upsource)

        self.check_open_reviews(project_upsource)

    def find_revision(self, issue_title, project_upsource):
        self.log.info(f'Finding a revision for {str(issue_title)} Issue')

        revision_id = None
        try:
            revision_list = self.review.get_filtered_revision_list(issue_title, project_upsource)
        except Exception as e:
            raise Exception(f'Failed to filtered_revision_list. Exception [{e}]')

        if revision_list is not None and 'revision' in revision_list:
            for revision in revision_list['revision']:
                if re.search('^Merge', revision['revisionCommitMessage']) is None:
                    revision_id = revision['revisionId']
                    break

        if revision_id is None:
            self.log.warning(f'Failed to received revision_id for {str(issue_title)} Issue. Review not created')
            return None
        else:
            return revision_id

    def create_review(self, revision_id, issue_id, issue_title, issue_summary, project_upsource):
        self.log.info(f'Creating a review for {str(issue_title)} Issue')
        try:
            review = self.review.create(revision_id, project_upsource)
        except Exception as e:
            raise Exception(f'Failed to create_review. Exception [{e}]')

        if len(review) > 0 and 'reviewId' in review:
            review_id = review['reviewId']['reviewId']
            self.issue.update_code_review_url(issue_id, self.review.get_review_url(review_id, project_upsource))
            review_title = f'{str(issue_title)} {str(issue_summary)}'

            try:
                self.review.rename(review_id, review_title, project_upsource)
            except Exception as e:
                raise Exception(f'Failed to rename_review. Exception [{e}]')

            self.set_branch_tracking(issue_title, review_id, project_upsource)
            if self.upsource_user_id is not None:
                try:
                    self.review.delete_default_reviewer(self.upsource_user_id, review_id, ParticipantRole.REVIEWER.value, project_upsource)
                except Exception as e:
                    raise Exception(f'Failed to delete_default_reviewer. Exception [{e}]')

            self.log.info(f'Review for {str(issue_title)} created')

    def set_branch_tracking(self, issue_title, review_id, project_upsource):
        try:
            branch_in_review = self.review.get_branch(issue_title, project_upsource)
        except Exception as e:
            if re.search(StatusCode.EXCEPTION.value, str(e)) is None:
                branch_in_review = None
            else:
                raise Exception(f'Failed to get_branch. Exception [{re.split("-", str(e))[1]}]')

        if branch_in_review is not None and 'branch' in branch_in_review:
            branch = branch_in_review['branch'][0]['name']
            try:
                self.review.start_branch_tracking(branch, review_id, project_upsource)
            except Exception as e:
                raise Exception(f'Failed to start_branch_tracking. Exception [{e}]')

    def check_open_reviews(self, project_upsource):
        review_list = self.review.get_list_on_query('state: open', project_upsource)
        if isinstance(review_list, list) and len(review_list) > 0 and 'reviewId' in review_list[0]:
            for review_data in review_list:
                if review_data['createdBy'] != self.upsource_user_id:
                    continue

                review_id = review_data['reviewId']['reviewId']
                issue_title = self.get_issue_title(review_id, review_data['title'], project_upsource)
                if issue_title is None:
                    self.log.warning(f'Failed to get_issue_title from review {review_id} {review_data["title"]}')
                    continue

                issue = self.issue.get_list_by_title(issue_title)
                if len(issue) > 0:
                    self.update_code_review_url_for_issue(review_id, issue, project_upsource)
                    issue_tasks = self.issue_task.find_issue_tasks(issue_title)
                    if len(issue_tasks) > 0:
                        self.update_code_review_url_for_issue_tasks(review_id, issue_tasks, project_upsource)
                        self.add_task_urls_to_description(review_data, review_id, issue_tasks, project_upsource)
                        self.remove_reviewers(review_data, review_id, issue_tasks, project_upsource)
                        self.add_reviewers(review_id, issue_tasks, project_upsource)
                        self.update_participant_status_for_review(review_id, issue_title, project_upsource)

                    issue_status = issue[0][self.issue.issue_fields.STATUS]
                    if issue_status in self.issue.issue_statuses.get_statuses_after_review():
                        try:
                            closed_review = self.review.close(review_id, project_upsource)
                        except Exception as e:
                            if re.search(StatusCode.EXCEPTION.value, e) is None:
                                closed_review = None
                            else:
                                raise Exception(f'Failed to close review. Exception [{re.split("-", e)[1]}]')

                        if closed_review is not None:
                            self.log.debug(f'Review {str(review_id)} closed for Issue {issue_title}')

    def get_issue_title(self, review_id, review_title, project_upsource):
        review_title = self.replace_non_breaking_space(review_id, review_title, project_upsource)
        issue_title = re.search(Integration.ISSUE_ID_PATTERN, review_title)
        if issue_title is not None:
            return issue_title.group()

    def replace_non_breaking_space(self, review_id, review_title, project_upsource):
        if re.search('\xa0', review_title) is not None:
            review_title = review_title.replace('\xa0', ' ')
            try:
                self.review.rename(review_id, review_title, project_upsource)
            except Exception as e:
                raise Exception(f'Failed to rename_review. Exception [{e}]')

        return review_title

    def update_code_review_url_for_issue(self, review_id, issue, project_upsource):
        issue_id = issue[0][self.issue.issue_fields.ID]
        issue_code_review_url = issue[0][self.issue.issue_fields.CODE_REVIEW_URL]
        if issue_code_review_url is None:
            self.issue.update_code_review_url(issue_id, self.review.get_review_url(review_id, project_upsource))

    def update_code_review_url_for_issue_tasks(self, review_id, issue_tasks, project_upsource):
        for issue_task in issue_tasks:
            issue_task_id = issue_task[self.issue_task.issue_task_fields.ID]
            issue_task_code_review_url = issue_task[self.issue_task.issue_task_fields.CODE_REVIEW_URL]

            if issue_task_code_review_url is None:
                self.issue_task.update_code_review_url(issue_task_id, self.review.get_review_url(review_id, project_upsource))

    def add_task_urls_to_description(self, review_data, review_id, issue_tasks, project_upsource):
        issue_task_url = f'{self.url_onevizion}trackor_types/{self.issue_task_trackor_type}/trackors.do?key='

        review_description = ''
        if 'description' in review_data:
            review_description = review_data['description']

        new_review_description = review_description
        if len(new_review_description) == 0:
            for issue_task in issue_tasks:
                issue_task_key = issue_task[self.issue_task.issue_task_fields.TITLE]
                issue_task_code_reviewer = issue_task[self.issue_task.issue_task_fields.REVIEWER]
                issue_task_status = issue_task[self.issue_task.issue_task_fields.STATUS]
                if issue_task_status != self.issue_task.issue_task_statuses.CANCELED:
                    new_review_description = f'[{issue_task_key}]({issue_task_url}{issue_task_key}) {issue_task_code_reviewer}\n{new_review_description}'
        else:
            split_review_description = re.split('\n', new_review_description)
            for description_line in split_review_description:
                if re.search(Integration.ISSUE_TASK_ID_IN_URL_PATTERN, description_line) is None:
                    break

                else:
                    is_issue_task_deleted = True
                    for issue_task in issue_tasks:
                        issue_task_key = issue_task[self.issue_task.issue_task_fields.TITLE]
                        issue_task_code_reviewer = str(issue_task[self.issue_task.issue_task_fields.REVIEWER])
                        issue_task_status = issue_task[self.issue_task.issue_task_fields.STATUS]
                        if issue_task_key in description_line:

                            if issue_task_status != self.issue_task.issue_task_statuses.CANCELED:

                                if issue_task_code_reviewer not in description_line:
                                    new_code_reviewer_in_description = f'[{issue_task_key}]({issue_task_url}{issue_task_key}) {issue_task_code_reviewer}'
                                    new_review_description = new_review_description.replace(description_line,
                                                                                            new_code_reviewer_in_description)

                                is_issue_task_deleted = False

                            break

                    if is_issue_task_deleted:
                        if f'{description_line}\n' in new_review_description:
                            new_review_description = new_review_description.replace(f'{description_line}\n', '')
                        else:
                            new_review_description = new_review_description.replace(description_line, '')

            for issue_task in issue_tasks:
                issue_task_key = issue_task[self.issue_task.issue_task_fields.TITLE]
                issue_task_code_reviewer = issue_task[self.issue_task.issue_task_fields.REVIEWER]
                issue_task_status = issue_task[self.issue_task.issue_task_fields.STATUS]
                if re.search(issue_task_key, new_review_description) is None \
                        and issue_task_status != self.issue_task.issue_task_statuses.CANCELED:
                    new_review_description = f'[{issue_task_key}]({issue_task_url}{issue_task_key}) {issue_task_code_reviewer}\n{new_review_description}'

        if review_description != new_review_description:
            try:
                self.review.update_review_description(review_id, new_review_description, project_upsource)
            except Exception as e:
                raise Exception(f'Failed to update_review_description. Exception [{e}]')

    def find_riviewers(self, review_data, state):
        reviewers_list = []
        if 'participants' in review_data:
            for participant in review_data['participants']:
                if participant['role'] == ParticipantRole.REVIEWER.value:
                    if state:
                        reviewers_list.append(
                            {'participant_id': participant['userId'], 'participant_state': participant['state']})
                    else:
                        reviewers_list.append(participant['userId'])

        return reviewers_list

    def remove_reviewers(self, review_data, review_id, issue_tasks, project_upsource):
        reviewers_list = self.find_riviewers(review_data, False)

        if len(reviewers_list) > 0:
            for user_id in reviewers_list:
                is_reviewer_deleted = True
                for reviewer in self.reviewers:
                    if reviewer[ReviewerField.ID.value] == user_id:
                        for issue_task in issue_tasks:
                            issue_task_code_reviewer = str(issue_task[self.issue_task.issue_task_fields.REVIEWER])
                            issue_task_status = issue_task[self.issue_task.issue_task_fields.STATUS]
                            if reviewer[ReviewerField.OV_NAME.value] in issue_task_code_reviewer \
                                    and issue_task_status != self.issue_task.issue_task_statuses.CANCELED:
                                is_reviewer_deleted = False
                                break

                        if is_reviewer_deleted:
                            try:
                                self.review.remove_reviewer(reviewer, review_id, project_upsource)
                            except Exception as e:
                                raise Exception(f'Failed to remove reviewer {str(reviewer[ReviewerField.OV_NAME.value])} to {str(review_id)} review. Exception [{e}]')

                        break

    def add_reviewers(self, review_id, issue_tasks, project_upsource):
        review_data = self.review.get_list_on_query(review_id, project_upsource)
        if isinstance(review_data, list) and len(review_data) > 0 and 'reviewId' in review_data[0]:
            reviewers_list = self.find_riviewers(review_data[0], False)

            for issue_task in issue_tasks:
                issue_task_code_reviewer = issue_task[self.issue_task.issue_task_fields.REVIEWER]
                issue_task_status = issue_task[self.issue_task.issue_task_fields.STATUS]
                if issue_task_code_reviewer is not None \
                        and issue_task_status != self.issue_task.issue_task_statuses.CANCELED:
                    for reviewer in self.reviewers:
                        if reviewer[ReviewerField.OV_NAME.value] in issue_task_code_reviewer and reviewer[ReviewerField.ID.value] not in reviewers_list:
                            try:
                                self.review.add_reviewer(reviewer, review_id, project_upsource)
                                reviewers_list.append(reviewer[ReviewerField.ID.value])
                            except Exception as e:
                                raise Exception(f'Failed to add reviewer {str(reviewer[ReviewerField.OV_NAME.value])} to {str(review_id)} review. Exception [{e}]')
                            break

    def update_participant_status_for_review(self, review_id, issue_title, project_upsource):
        review_data = self.review.get_list_on_query(review_id, project_upsource)
        if isinstance(review_data, list) and len(review_data) > 0 and 'reviewId' in review_data[0]:
            reviewers_list = self.find_riviewers(review_data[0], True)

        if len(reviewers_list) > 0:
            for participant in reviewers_list:
                participant_id = participant['participant_id']
                participant_state = participant['participant_state']

                for reviewer in self.reviewers:
                    if participant_id == reviewer[ReviewerField.ID.value]:
                        is_accepted = True
                        is_rejected = False
                        issue_tasks = self.issue_task.find_issue_tasks_for_reviewer(issue_title, reviewer[ReviewerField.OV_NAME.value],
                                                                                    self.issue_task.issue_task_statuses.get_statuses_for_reviewer())
                        if len(issue_tasks) > 0:
                            for issue_task in issue_tasks:
                                issue_task_status = issue_task[self.issue_task.issue_task_fields.STATUS]

                                if issue_task_status in (self.issue_task.issue_task_statuses.AWAITING_RESPONSE,
                                                         self.issue_task.issue_task_statuses.CONCERN_RAISED):
                                    if participant_state != ParticipantState.REJECTED.value \
                                            and issue_task_status != self.issue_task.issue_task_statuses.CONCERN_RAISED:
                                        self.review.update_participant_status(reviewer, ParticipantState.REJECTED.value, review_id, 
                                                                              project_upsource)
                                        self.issue_task.update_concern_raised(issue_task[self.issue_task.issue_task_fields.ID])
                                    is_rejected = True
                                    is_accepted = False
                                    break

                                if issue_task_status != self.issue_task.issue_task_statuses.COMPLETED:
                                    is_accepted = False

                            if is_accepted and participant_state != ParticipantState.ACCEPTED.value:
                                issue_tasks_in_progress = self.issue_task.find_issue_tasks_for_reviewer(issue_title,
                                                                                                        reviewer[ReviewerField.OV_NAME.value],
                                                                                                        self.issue_task.issue_task_statuses.IN_PROGRESS)
                                if len(issue_tasks_in_progress) == 0:
                                    self.review.update_participant_status(reviewer, ParticipantState.ACCEPTED.value, review_id,
                                                                          project_upsource)

                            if is_rejected is False and is_accepted is False and participant_state != ParticipantState.READ.value:
                                self.review.update_participant_status(reviewer, ParticipantState.READ.value, review_id,
                                                                      project_upsource)

                        break


class Issue:
    def __init__(self, url_onevizion, login_onevizion, pass_onevizion, issue_trackor_type,
                 issue_statuses, issue_fields):
        self.issue_statuses = IssueStatuses(issue_statuses)
        self.issue_fields = IssueFields(issue_fields)
        self.issue_service = onevizion.Trackor(trackorType=issue_trackor_type, URL=url_onevizion,
                                               userName=login_onevizion, password=pass_onevizion)

    def get_list_for_review(self, product_onevizion):
        self.issue_service.read(
            filters={self.issue_fields.PRODUCT: product_onevizion,
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
            filters={self.issue_fields.TITLE: issue_title},
            fields=[self.issue_fields.TITLE, self.issue_fields.STATUS, self.issue_fields.CODE_REVIEW_URL]
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
        self.issue_task_trackor_type = issue_task_trackor_type
        self.issue_task_service = onevizion.Trackor(trackorType=issue_task_trackor_type, URL=url_onevizion,
                                                    userName=login_onevizion, password=pass_onevizion)

    def find_issue_tasks(self, issue_title):
        self.issue_task_service.read(
            filters={self.issue_task_fields.TYPE: self.issue_task_types.CODE_REVIEW_LABEL,
                     self.issue_task_fields.ISSUE: issue_title},
            fields=[self.issue_task_fields.REVIEWER, self.issue_task_fields.STATUS, self.issue_task_fields.TITLE,
                    self.issue_task_fields.CODE_REVIEW_URL])

        return self.issue_task_service.jsonData

    def find_issue_tasks_for_reviewer(self, issue_title, reviewer, status):
        self.issue_task_service.read(
            filters={self.issue_task_fields.TYPE: self.issue_task_types.CODE_REVIEW_LABEL,
                     self.issue_task_fields.ISSUE: issue_title,
                     self.issue_task_fields.REVIEWER: reviewer,
                     self.issue_task_fields.STATUS: status},
            fields=[self.issue_task_fields.STATUS])

        return self.issue_task_service.jsonData

    def update_code_review_url(self, issue_task_id, code_review_url):
        self.issue_task_service.update(
            trackorId=issue_task_id,
            fields={self.issue_task_fields.CODE_REVIEW_URL: code_review_url}
        )

    def update_concern_raised(self, issue_task_id):
        self.issue_task_service.update(
            trackorId=issue_task_id,
            fields={self.issue_task_fields.CONCERN_RAISED: '1'}
        )


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
        self.CONCERN_RAISED = issue_task_fields[IssueTaskField.CONCERN_RAISED.value]


class IssueTaskTypes:
    def __init__(self, issue_task_types):
        self.CODE_REVIEW = issue_task_types[IssueTaskType.CODE_REVIEW.value]
        self.CODE_REVIEW_LABEL = issue_task_types[IssueTaskType.CODE_REVIEW_LABEL.value]


class IssueTaskStatuses:
    def __init__(self, issue_task_statuses):
        self.OPENED = issue_task_statuses[IssueTaskStatus.OPENED.value]
        self.COMPLETED = issue_task_statuses[IssueTaskStatus.COMPLETED.value]
        self.AWAITING_RESPONSE = issue_task_statuses[IssueTaskStatus.AWAITING_RESPONSE.value]
        self.IN_PROGRESS = issue_task_statuses[IssueTaskStatus.IN_PROGRESS.value]
        self.CONCERN_RAISED = issue_task_statuses[IssueTaskStatus.CONCERN_RAISED.value]
        self.CANCELED = issue_task_statuses[IssueTaskStatus.CANCELED.value]

    def get_statuses_for_reviewer(self):
        statuses = f'{self.OPENED},{self.COMPLETED},{self.AWAITING_RESPONSE},{self.CONCERN_RAISED}'
        return statuses


class Review:
    LIMIT = 100

    def __init__(self, url_upsource, user_name_upsource, token_upsource, reviewers, logger):
        self.url_upsource = url_upsource
        self.user_name_upsource = user_name_upsource
        self.reviewers = reviewers
        self.headers = {'Content-type': 'application/json', 'Content-Encoding': 'utf-8', 'Authorization': f'Bearer {token_upsource}'}
        self.log = logger

    def get_filtered_revision_list(self, issue_title, project_upsource):
        url = f'{self.url_upsource}~rpc/getRevisionsListFiltered'
        data = {"projectId": project_upsource, "limit": Review.LIMIT, "query": issue_title}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok:
            return answer.json()['result']
        else:
            self.log.warning(f'Failed to filtered_revision_list. Exception [{answer.text}]')
            if answer.status_code == StatusCode.EXCEPTION.value:
                raise Exception(answer.text)

            return None

    def close(self, review_id, project_upsource):
        url = f'{self.url_upsource}~rpc/closeReview'
        data = {"reviewId": {"projectId": project_upsource, "reviewId": review_id}, "isFlagged": True}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok:
            return answer
        else:
            self.log.warning(f'Failed to close review. Exception [{answer.text}]')
            if answer.status_code == StatusCode.EXCEPTION.value:
                raise Exception(f'{answer.status_code}-{answer.text}')
            raise Exception(f'Failed to close review. Exception [{answer.text}]')

    def get_branch(self, issue_title, project_upsource):
        url = f'{self.url_upsource}~rpc/getBranches'
        data = {"projectId": project_upsource, "limit": Review.LIMIT, "query": issue_title}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok:
            return answer.json()['result']
        else:
            self.log.warning(f'Failed to get_branch. Exception [{answer.text}]')
            if answer.status_code == StatusCode.EXCEPTION.value:
                raise Exception(f'{answer.status_code}-{answer.text}')
            raise Exception(f'Failed to get_branch. Exception [{answer.text}]')

    def start_branch_tracking(self, branch, review_id, project_upsource):
        url = f'{self.url_upsource}~rpc/startBranchTracking'
        data = {"reviewId": {"projectId": project_upsource, "reviewId": review_id}, "branch": branch}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok == False:
            self.log.warning(f'Failed to start_branch_tracking. Exception [{answer.text}]')
            if answer.status_code == StatusCode.EXCEPTION.value:
                raise Exception(answer.text)

    def find_user_in_upsource(self, reviewer_name, project_upsource):
        url = f'{self.url_upsource}~rpc/findUsers'
        data = {'projectId': project_upsource, 'pattern': reviewer_name, 'limit': Review.LIMIT}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok:
            result = answer.json()['result']
            if len(result) > 0:
                return result
            else:
                raise Exception(answer.text)
        else:
            raise Exception(f'{answer.status_code}-{answer.text}')

    def get_upsource_user_id(self, project_upsource):
        try:
            upsource_user = self.find_user_in_upsource(self.user_name_upsource, project_upsource)
        except Exception as e:
            self.log.error(f'Failed to get_upsource_user_id - {self.user_name_upsource}. Exception [{e}]')
            raise Exception(f'Failed to get_upsource_user_id - {self.user_name_upsource}. Exception [{e}]')

        if upsource_user is not None and 'infos' in upsource_user:
            return upsource_user['infos'][0]['userId']
        else:
            raise Exception(f'Failed to get_upsource_user_id - {self.user_name_upsource}')

    def update_participant_status(self, reviewer, state, review_id, project_upsource):
        try:
            self.update_participant_in_review(reviewer, state, review_id, project_upsource)
        except Exception as e:
            raise Exception(f'Failed to update_participant_status for reviewer {str(reviewer[ReviewerField.OV_NAME.value])} to {str(review_id)} review. Exception [{e}]')

    def update_participant_in_review(self, reviewer, state, review_id, project_upsource):
        url = f'{self.url_upsource}~rpc/updateParticipantInReview'
        data = {"reviewId": {"projectId": project_upsource, "reviewId": review_id}, "state": state,
                "userId": reviewer[ReviewerField.ID.value]}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok:
            self.log.info(f'Status for reviewer {str(reviewer[ReviewerField.OV_NAME.value])} has been changed to {state}')
        else:
            self.log.warning(f'Failed to update_participant_status for reviewer {str(reviewer[ReviewerField.OV_NAME.value])} to {str(review_id)} review. Exception [{answer.text}]')
            if answer.status_code == StatusCode.EXCEPTION.value:
                raise Exception(answer.text)

    def add_reviewer(self, reviewer, review_id, project_upsource):
        url = f'{self.url_upsource}~rpc/addParticipantToReview'
        data = {"reviewId": {"projectId": project_upsource, "reviewId": review_id},
                "participant": {"userId": reviewer[ReviewerField.ID.value], "role": ParticipantRole.REVIEWER.value}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok:
            self.log.info(f'Reviewer {str(reviewer[ReviewerField.OV_NAME.value])} was added to {str(review_id)} review')
        else:
            self.log.warning(f'Failed to add reviewer {str(reviewer[ReviewerField.OV_NAME.value])} to {str(review_id)} review. Exception [{answer.text}]')
            if answer.status_code == StatusCode.EXCEPTION.value:
                raise Exception(answer.text)

    def remove_reviewer(self, reviewer, review_id, project_upsource):
        url = f'{self.url_upsource}~rpc/removeParticipantFromReview'
        data = {"reviewId": {"projectId": project_upsource, "reviewId": review_id},
                "participant": {"userId": reviewer[ReviewerField.ID.value], "role": ParticipantRole.REVIEWER.value}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok:
            self.log.info(f'Reviewer {str(reviewer[ReviewerField.OV_NAME.value])} removed from {str(review_id)} review')
        else:
            self.log.warning(f'Failed to remove reviewer {str(reviewer[ReviewerField.OV_NAME.value])} to {str(review_id)} review. Exception [{answer.text}]')
            if answer.status_code == StatusCode.EXCEPTION.value:
                raise Exception(answer.text)

    def get_list_on_query(self, query, project_upsource):
        try:
            review_data = self.get_reviews(query, project_upsource)
        except Exception as e:
            raise Exception(f'Failed to get_reviews. Exception [{e}]')

        return review_data

    def get_reviews(self, query, project_upsource):
        url = f'{self.url_upsource}~rpc/getReviews'
        data = {"projectId": project_upsource, "limit": Review.LIMIT, "query": query}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok:
            if 'reviews' in answer.json()['result']:
                return answer.json()['result']['reviews']
            else:
                return answer.json()
        else:
            self.log.warning(f'Failed to get_reviews. Exception [{answer.text}]')
            if answer.status_code == StatusCode.EXCEPTION.value:
                raise Exception(answer.text)

            return None

    def delete_default_reviewer(self, user_id, review_id, role_in_review, project_upsource):
        url = f'{self.url_upsource}~rpc/removeParticipantFromReview'
        data = {"reviewId": {"projectId": project_upsource, "reviewId": review_id},
                "participant": {"userId": user_id, "role": role_in_review}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok == False:
            self.log.warning(f'Failed to delete_default_reviewer. Exception [{answer.text}]')
            if answer.status_code == StatusCode.EXCEPTION.value:
                raise Exception(answer.text)

    def rename(self, review_id, title, project_upsource):
        url = f'{self.url_upsource}~rpc/renameReview'
        data = {"reviewId": {"projectId": project_upsource, "reviewId": review_id},
                "text": title}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok == False:
            self.log.warning(f'Failed to rename_review. Exception [{answer.text}]')
            if answer.status_code == StatusCode.EXCEPTION.value:
                raise Exception(answer.text)

    def create(self, revision_id, project_upsource):
        url = f'{self.url_upsource}~rpc/createReview'
        data = {"projectId": project_upsource, "revisions": revision_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok:
            return answer.json()['result']
        else:
            self.log.warning(f'Failed to create_review. Exception [{answer.text}]')
            if answer.status_code == StatusCode.EXCEPTION.value:
                raise Exception(answer.text)

            return None

    def get_review_url(self, review_id, project_upsource):
        return f'{self.url_upsource}{project_upsource}/review/{review_id}'

    def update_review_description(self, review_id, description, project_upsource):
        url = f'{self.url_upsource}~rpc/editReviewDescription'
        data = {"reviewId": {"projectId": project_upsource, "reviewId": review_id},
                "text": description}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data))
        if answer.ok == False:
            self.log.warning(f'Failed to update_review_description. Exception [{answer.text}]')
            if answer.status_code == StatusCode.EXCEPTION.value:
                raise Exception(answer.text)


class IssueStatus(Enum):
    TEST = 'test'
    MERGE = 'readyForMerge'
    CLOSED = 'closed'
    COMPLETED = 'completed'
    CANCELED = 'canceled'
    READY_FOR_REVIEW = 'readyForReview'


class IssueTaskStatus(Enum):
    OPENED = 'opened'
    COMPLETED = 'completed'
    IN_PROGRESS = 'inProgress'
    AWAITING_RESPONSE = 'awaitingResponse'
    CONCERN_RAISED = 'concernRaised'
    CANCELED = 'canceled'


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
    CONCERN_RAISED = 'concernRaised'


class IssueTaskType(Enum):
    CODE_REVIEW = 'codeReview'
    CODE_REVIEW_LABEL = 'codeReviewLabel'


class ReviewerField(Enum):
    ID = 'reviewer_id'
    OV_NAME = 'reviewer_ov_name'

class ParticipantState(Enum):
    READ = 2
    ACCEPTED = 3
    REJECTED = 4


class ParticipantRole(Enum):
    REVIEWER = 2


class StatusCode(Enum):
    UNAUTHORIZED = 401
    EXCEPTION = 555
