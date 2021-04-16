from flask import Flask, request, make_response
from functools import wraps
from enum import Enum

import json


app = Flask(__name__)

def auth_required(f):
    @wraps(f) 
    def decorated(*args, **kwargs):
        auth = request.authorization
        with open('settings.json', 'rb') as PFile:
            password_data = json.loads(PFile.read().decode('utf-8'))

        if auth.username == password_data['loginUpsource'] \
            and auth.password == password_data['passUpsource']:
            return f(*args, **kwargs)

        return make_response('Authentication failed', StatusCode.UNAUTHORIZED.value)

    return decorated

@app.route('/~rpc/getRevisionsListFiltered',  methods=['POST'])
@auth_required
def get_filtered_revision_list():
    query = request.get_json()['query']

    if query not in (Issue.TEST_ISSUE_2.issue_id, Issue.TEST_ISSUE_1.issue_id):
        return make_response(f'Revision for {query} not found', StatusCode.EXCEPTION.value)

    if query == Issue.TEST_ISSUE_2.issue_id:
        json_data = {'result': {'revision': [{'revisionId': Review.TEST_REVIEW_2.review_id, 
                'revisionCommitMessage': f'{Issue.TEST_ISSUE_2.issue_id} {Issue.TEST_ISSUE_2.summary}\n'}]}}
    elif query == Issue.TEST_ISSUE_1.issue_id:
        json_data = {'result': {'revision': [{'revisionId': Review.TEST_REVIEW_1.review_id, 
                'revisionCommitMessage': f'{Issue.TEST_ISSUE_1.issue_id} {Issue.TEST_ISSUE_1.summary}\n'}]}}
    else:
        json_data = {'result': {'query': f'{query}'}}

    return json_data

@app.route('/~rpc/closeReview',  methods=['POST'])
@auth_required
def close_review():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in (Review.TEST_REVIEW_1.review_key, Review.TEST_REVIEW_2.review_key):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id

@app.route('/~rpc/getBranches',  methods=['POST'])
@auth_required
def get_branch():
    query = request.get_json()['query']

    if query == Issue.TEST_ISSUE_2.issue_id:
        json_data =  {'result': {'defaultBranch': 'master'}}
    elif query == Issue.TEST_ISSUE_1.issue_id:
        json_data = {'result': {'branch': [{'name': Issue.TEST_ISSUE_1.issue_id}]}}
    else:
        return make_response(f'Branch {query} not found', StatusCode.EXCEPTION.value)

    return json_data

@app.route('/~rpc/startBranchTracking',  methods=['POST'])
@auth_required
def start_branch_tracking():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in (Review.TEST_REVIEW_1.review_key, Review.TEST_REVIEW_2.review_key):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id

@app.route('/~rpc/findUsers',  methods=['POST'])
@auth_required
def find_users():
    pattern = request.get_json()['pattern']

    if pattern == User.TEST_USER_1.user_name:
        json_data = {'result': {'infos': [{'userId': User.TEST_USER_1.user_id}]}}
    elif pattern == User.TEST_USER_2.user_name:
        json_data = {'result': {'infos': [{'userId': User.TEST_USER_2.user_id}]}}
    elif pattern == User.TEST_USER_3.user_name:
        json_data = {'result': {'infos': [{'userId': User.TEST_USER_3.user_id}]}}
    else:
        return make_response(f'Cannot resolve pattern {pattern}', StatusCode.EXCEPTION.value)

    return json_data

@app.route('/~rpc/updateParticipantInReview',  methods=['POST'])
@auth_required
def update_participant_status():
    review_id = request.get_json()['reviewId']['reviewId']
    user_id = request.get_json()['userId']

    if review_id not in (Review.TEST_REVIEW_1.review_key, Review.TEST_REVIEW_2.review_key):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    if user_id not in (User.TEST_USER_1.user_id, User.TEST_USER_2.user_id, User.TEST_USER_3.user_id):
        return make_response(f'Cannot resolve user id {user_id}', StatusCode.EXCEPTION.value)

    return user_id

@app.route('/~rpc/addParticipantToReview',  methods=['POST'])
@auth_required
def add_reviewer():
    review_id = request.get_json()['reviewId']['reviewId']
    user_id = request.get_json()['participant']['userId']

    if review_id not in (Review.TEST_REVIEW_1.review_key, Review.TEST_REVIEW_2.review_key):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    if user_id not in (User.TEST_USER_1.user_id, User.TEST_USER_2.user_id, User.TEST_USER_3.user_id):
        return make_response(f'Cannot resolve user id {user_id}', StatusCode.EXCEPTION.value)

    return user_id

@app.route('/~rpc/removeParticipantFromReview',  methods=['POST'])
@auth_required
def remove_reviewer():
    review_id = request.get_json()['reviewId']['reviewId']
    user_id = request.get_json()['participant']['userId']

    if review_id not in (Review.TEST_REVIEW_1.review_key, Review.TEST_REVIEW_2.review_key):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    if user_id not in (User.TEST_USER_1.user_id, User.TEST_USER_2.user_id, User.TEST_USER_3.user_id):
        return make_response(f'Cannot resolve user id {user_id}', StatusCode.EXCEPTION.value)

    return user_id

@app.route('/~rpc/getReviews',  methods=['POST'])
@auth_required
def get_reviews():
    with open('settings.json', 'rb') as PFile:
        settings_url = json.loads(PFile.read().decode('utf-8'))['urlOneVizion']

    REVIEW_JSON_DATA_1 = {'reviewId':{'projectId':'blank','reviewId':Review.TEST_REVIEW_1.review_key},
                          'title':f'{Issue.TEST_ISSUE_1.issue_id} {Issue.TEST_ISSUE_1.summary}',
                          'description':f'[{Issue.TEST_ISSUE_1.issue_id}-64]({settings_url}trackor_types/Issue_Task/trackors.do?key={Issue.TEST_ISSUE_1.issue_id}-64) amoiseenko\n \
                                          [{Issue.TEST_ISSUE_1.issue_id}-62]({settings_url}trackor_types/Issue_Task/trackors.do?key={Issue.TEST_ISSUE_1.issue_id}-62) vadim.glebov',
                          'participants':[{'userId':User.TEST_USER_3.user_id,'role':2,'state':2},
                                          {'userId':User.TEST_USER_1.user_id,'role':2,'state':2},
                                          {'userId':User.TEST_USER_2.user_id,'role':2,'state':2},
                                          {'userId':User.TEST_USER_4.user_id,'role':1,'state':2}],
                          'state':1,'createdBy':User.TEST_USER_3.user_id}
    REVIEW_JSON_DATA_2 = {'reviewId':{'projectId':'blank','reviewId':Review.TEST_REVIEW_2.review_key},
                          'title':f'{Issue.TEST_ISSUE_2.issue_id} {Issue.TEST_ISSUE_2.summary}',
                          'participants':[{'userId':User.TEST_USER_1.user_id,'role':1,'state':1}],
                          'state':1,'createdBy':User.TEST_USER_3.user_id}
  

    query = request.get_json()['query']

    if query not in (Issue.TEST_ISSUE_2.issue_id, Issue.TEST_ISSUE_1.issue_id, Review.TEST_REVIEW_1.review_key, Review.TEST_REVIEW_2.review_key, 'state: open'):
        return make_response(f'Review for {query} not found', StatusCode.EXCEPTION.value)


    if query == Issue.TEST_ISSUE_2.issue_id:
        json_data = {'result': {'hasMore': False, 'totalCount': 0}}
    elif query == Review.TEST_REVIEW_2.review_key:
        json_data = {'result':{'reviews':[REVIEW_JSON_DATA_2]}}
    elif query in (Issue.TEST_ISSUE_1.issue_id, Review.TEST_REVIEW_1.review_key):
        json_data = {'result':{'reviews':[REVIEW_JSON_DATA_1]}}
    elif query == 'state: open':
        json_data = {'result':{'reviews':[REVIEW_JSON_DATA_1, REVIEW_JSON_DATA_2]}}
    else:
        json_data = {'result': {'hasMore': False, 'totalCount': 0}}

    return json_data

@app.route('/~rpc/renameReview',  methods=['POST'])
@auth_required
def rename_review():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in (Review.TEST_REVIEW_1.review_key, Review.TEST_REVIEW_2.review_key):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id

@app.route('/~rpc/createReview',  methods=['POST'])
@auth_required
def create_review():
    revisions = request.get_json()['revisions']

    if revisions == Review.TEST_REVIEW_2.review_id:
        json_data = {'result':{
                'reviewId':{'projectId':'blank','reviewId':Review.TEST_REVIEW_2.review_key},
                'title':f'{Issue.TEST_ISSUE_2.issue_id} {Issue.TEST_ISSUE_2.summary}',
                'participants':[{'userId':User.TEST_USER_3.user_id,'role':2,'state':1},
                                {'userId':User.TEST_USER_1.user_id,'role':1,'state':1}],
                'state':1,'createdBy':User.TEST_USER_3.user_id}}
    elif revisions == Review.TEST_REVIEW_1.review_id:
        return make_response(f'Cannot create review because revision {revisions} is already in review Review(reviewId=ReviewId[{Review.TEST_REVIEW_1.review_id}], \
                                title=\'{Issue.TEST_ISSUE_1.issue_id} {Issue.TEST_ISSUE_1.summary}\'', StatusCode.EXCEPTION.value)
    else:
        return make_response(f'Cannot resolve revision {revisions} in project blank', StatusCode.EXCEPTION.value)

    return json_data

@app.route('/~rpc/editReviewDescription',  methods=['POST'])
@auth_required
def update_review_description():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in (Review.TEST_REVIEW_1.review_key, Review.TEST_REVIEW_2.review_key):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id


class StatusCode(Enum):
    UNAUTHORIZED = 401
    EXCEPTION = 555


class Review(Enum):

    def __init__(self, review_id, review_key):
        self.review_id = review_id
        self.review_key = review_key

    TEST_REVIEW_1 = ('6c3fd124ae40d499e7c27d22381c8a07e8f78afa', 'BLNK-CR-127')
    TEST_REVIEW_2 = ('5de06f7e6562b385e707b9beee3c559d1a237184', 'BLNK-CR-128')


class Issue(Enum):

    def __init__(self, issue_id, summary):
        self.issue_id = issue_id
        self.summary = summary

    TEST_ISSUE_1 = ('Depl-125306', 'Configure \'blank\' project in AWS')
    TEST_ISSUE_2 = ('IHub-146144', 'Test Upsource integration')


class User(Enum):

    def __init__(self, user_id, user_name):
        self.user_id = user_id
        self.user_name = user_name

    TEST_USER_1 = ('4006a614-5f72-4c75-a6e7-389e49ccb4fa', 'asmoiseenko')
    TEST_USER_2 = ('dfed774e-37c7-49bd-9059-6aa51bad1bb8', 'Vadim')
    TEST_USER_3 = ('30c91c19-e69f-4de9-92a1-7da68aec71af', 'Ilya Emelyanov')
    TEST_USER_4 = ('795d4839-3e99-4b76-b35c-e70f80ab856c', '')


if __name__ == '__main__':
    app.run(debug=True)