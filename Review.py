from UrlSetting import UrlSetting
from IntegrationLog import IntegrationLog
from requests.auth import HTTPBasicAuth
import requests
import json


class Review:
    def __init__(self, url_upsource, user_name_upsource, login_upsource, pass_upsource, project_upsource, review_scopes):        
        self.url_upsource = UrlSetting().url_setting(url_upsource)
        self.user_name_upsource = user_name_upsource
        self.project_upsource = project_upsource
        self.auth_upsource = HTTPBasicAuth(login_upsource, pass_upsource)
        self.review_scopes = review_scopes
        self.headers = {'Content-type':'application/json','Content-Encoding':'utf-8'}
        self.log = IntegrationLog().get_logger()

    def filtered_revision_list(self, issue_title):
        url = self.url_upsource + '~rpc/getRevisionsListFiltered'
        data = {"projectId":self.project_upsource, "limit":100, "query":issue_title}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']
        else:
            self.log.warning('Failed to filtered_revision_list. Exception [%s]' % str(answer.text))
            return None

    def close_or_reopen_review(self, status, review_id):
        url = self.url_upsource + '~rpc/closeReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":review_id}, "isFlagged":status}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer
        else:
            raise Exception(answer.text)

    def stop_branch_tracking(self, branch, review_id):
        url = self.url_upsource + '~rpc/stopBranchTracking'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":review_id}, "branch":branch}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to stop_branch_tracking. Exception [%s]' % str(answer.text)) 

    def get_branch(self, issue_title):
        url = self.url_upsource + '~rpc/getBranches'
        data = {"projectId":self.project_upsource, "limit":100, "query":issue_title}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']
        else:
            raise Exception(answer.text)

    def find_user_in_upsource(self, reviewer_name):
        url = self.url_upsource + '~rpc/findUsers'
        data = {'projectId': self.project_upsource, 'pattern': reviewer_name, 'limit': 100}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']
        else:
            raise Exception(answer.text)

    def get_revision_in_review(self, revision_id):
        url = self.url_upsource + '~rpc/getRevisionReviewInfo'
        data = {"projectId": self.project_upsource, "revisionId": revision_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']['reviewInfo'][0]
        else:
            raise Exception(answer.text)

    def add_revision(self, revision_id, review_id):
        url = self.url_upsource + '~rpc/addRevisionToReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":review_id},
                "revisionId":revision_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to add_revision. Exception [%s]' % str(answer.text))

    def update_participant_status(self, state, reviewer_token, review_id):
        url = self.url_upsource + '~rpc/updateParticipantInReview'
        data = {"reviewId": {"projectId": self.project_upsource, "reviewId": review_id}, "state": state}
        headers_participant = {'Content-type': 'application/json', 'Content-Encoding': 'utf-8', 'Authorization': 'Bearer '}
        headers_participant['Authorization'] = 'Bearer ' + reviewer_token
        answer = requests.post(url, headers=headers_participant, data=json.dumps(data))
        if answer.ok == False:
            self.log.warning('Failed to update_participant_status. Exception [%s]' % str(answer.text))

    def get_review_summary_changes(self, review_id, revision_id_list):
        url = self.url_upsource + '~rpc/getReviewSummaryChanges'
        if revision_id_list == '':
            data = {"reviewId":{"projectId":self.project_upsource, "reviewId":review_id}, 
                    "revisions":{"selectAll":True}}
        else:
            data = {"reviewId": {"projectId": self.project_upsource, "reviewId": review_id}, 
                    "revisions": {"revisions": revision_id_list}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            if 'diff' in answer.json()['result']['diff']:
                return answer.json()['result']['diff']['diff']
            else:
                return []
        else:
            self.log.warning('Failed to get_review_summary_changes. Exception [%s]' % str(answer.text))
            return []

    def add_reviewer(self, reviewer_id, review_id):
        url = self.url_upsource + '~rpc/addParticipantToReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":review_id}, "participant":{"userId":reviewer_id, "role":2}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to add_reviewer. Exception [%s]' % str(answer.text))

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
            self.log.warning('Failed to get_reviews. Exception [%s]' % str(answer.text))
            return None

    def delete_default_reviewer(self, user_id, review_id, role_in_review):
        url = self.url_upsource + '~rpc/removeParticipantFromReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":review_id}, 
                "participant":{"userId":user_id, "role": role_in_review}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to delete_default_reviewer. Exception [%s]' % str(answer.text))

    def rename_review(self, review_id, issue_title, issue_summary):
        url = self.url_upsource + '~rpc/renameReview'
        data = {"reviewId":{"projectId":self.project_upsource, "reviewId":review_id}, "text":str(issue_title) + ' ' + str(issue_summary)}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to rename_review. Exception [%s]' % str(answer.text))

    def create_review(self, revision_id):
        url = self.url_upsource + '~rpc/createReview'
        data = {"projectId":self.project_upsource, "revisions":revision_id}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer
        else:
            self.log.warning('Failed to create_review. Exception [%s]' % str(answer.text))
            return None

    def create_or_edit_review_label(self, label_name, label_color):
        url = self.url_upsource + '~rpc/createOrEditReviewLabel'
        data = {'projectId': self.project_upsource, 'label': {'id': label_name, 'name': label_name, 'colorId': label_color}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to create_or_edit_review_label. Exception [%s]' % str(answer.text))

    def get_review_labels(self):
        url = self.url_upsource + '~rpc/getReviewLabels'
        data = {"projectId":self.project_upsource}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok:
            return answer.json()['result']
        else:
            self.log.warning('Failed to get_review_labels. Exception [%s]' % str(answer.text))
            return None

    def add_or_remove_review_label(self, review_id, label_id, label_name, action):
        if action == 'add':
            url = self.url_upsource + '~rpc/addReviewLabel'
        if action == 'remove':
            url = self.url_upsource + '~rpc/removeReviewLabel'
        data = {"projectId":self.project_upsource, "reviewId":{"projectId":self.project_upsource, "reviewId":review_id}, 
                "label":{"id":label_id, "name":label_name}}
        answer = requests.post(url, headers=self.headers, data=json.dumps(data), auth=self.auth_upsource)
        if answer.ok == False:
            self.log.warning('Failed to add_or_remove_review_label. Exception [%s]' % str(answer.text))
