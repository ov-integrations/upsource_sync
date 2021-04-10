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

@app.route('/')
@auth_required
def main():
    return 'You are logged in'

@app.route('/~rpc/getRevisionsListFiltered',  methods=['POST'])
@auth_required
def get_filtered_revision_list():
    query = request.get_json()['query']

    if query not in (Issue.ID_TEST_2.value, Issue.ID_TEST_1.value):
        return make_response(f'Revision for {query} not found', StatusCode.EXCEPTION.value)

    if query == Issue.ID_TEST_2.value:
        json_data = {'result': {'revision': [{'revisionId': Review.ID_TEST_2.value, 
                'revisionCommitMessage': f'{Issue.ID_TEST_2.value} {Issue.SUMMARY_TEST_2.value}\n'}]}}
    elif query == Issue.ID_TEST_1.value:
        json_data = {'result': {'revision': [{'revisionId': Review.ID_TEST_1.value, 
                'revisionCommitMessage': f'{Issue.ID_TEST_1.value} {Issue.SUMMARY_TEST_1.value}\n'}]}}
    else:
        json_data = {'result': {'query': f'{query}'}}

    return json_data

@app.route('/~rpc/closeReview',  methods=['POST'])
@auth_required
def close_review():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in (Review.SUMMARY_TEST_1.value, Review.SUMMARY_TEST_2.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id

@app.route('/~rpc/getBranches',  methods=['POST'])
@auth_required
def get_branch():
    query = request.get_json()['query']

    if query == Issue.ID_TEST_2.value:
        json_data =  {'result': {'defaultBranch': 'master'}}
    elif query == Issue.ID_TEST_1.value:
        json_data = {'result': {'branch': [{'name': Issue.ID_TEST_1.value}]}}
    else:
        return make_response(f'Branch {query} not found', StatusCode.EXCEPTION.value)

    return json_data

@app.route('/~rpc/startBranchTracking',  methods=['POST'])
@auth_required
def start_branch_tracking():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in (Review.SUMMARY_TEST_1.value, Review.SUMMARY_TEST_2.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id

@app.route('/~rpc/findUsers',  methods=['POST'])
@auth_required
def find_users():
    pattern = request.get_json()['pattern']

    if pattern == User.NAME_TEST_1.value:
        json_data = {'result': {'infos': [{'userId': User.ID_TEST_1.value}]}}
    elif pattern == User.NAME_TEST_2.value:
        json_data = {'result': {'infos': [{'userId': User.ID_TEST_2.value}]}}
    elif pattern == User.NAME_TEST_3.value:
        json_data = {'result': {'infos': [{'userId': User.ID_TEST_3.value}]}}
    else:
        return make_response(f'Cannot resolve pattern {pattern}', StatusCode.EXCEPTION.value)

    return json_data

@app.route('/~rpc/updateParticipantInReview',  methods=['POST'])
@auth_required
def update_participant_status():
    review_id = request.get_json()['reviewId']['reviewId']
    user_id = request.get_json()['userId']

    if review_id not in (Review.SUMMARY_TEST_1.value, Review.SUMMARY_TEST_2.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    if user_id not in (User.ID_TEST_1.value, User.ID_TEST_2.value, User.ID_TEST_3.value):
        return make_response(f'Cannot resolve user id {user_id}', StatusCode.EXCEPTION.value)

    return user_id

@app.route('/~rpc/addParticipantToReview',  methods=['POST'])
@auth_required
def add_reviewer():
    review_id = request.get_json()['reviewId']['reviewId']
    user_id = request.get_json()['participant']['userId']

    if review_id not in (Review.SUMMARY_TEST_1.value, Review.SUMMARY_TEST_2.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    if user_id not in (User.ID_TEST_1.value, User.ID_TEST_2.value, User.ID_TEST_3.value):
        return make_response(f'Cannot resolve user id {user_id}', StatusCode.EXCEPTION.value)

    return user_id

@app.route('/~rpc/removeParticipantFromReview',  methods=['POST'])
@auth_required
def remove_reviewer():
    review_id = request.get_json()['reviewId']['reviewId']
    user_id = request.get_json()['participant']['userId']

    if review_id not in (Review.SUMMARY_TEST_1.value, Review.SUMMARY_TEST_2.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    if user_id not in (User.ID_TEST_1.value, User.ID_TEST_2.value, User.ID_TEST_3.value):
        return make_response(f'Cannot resolve user id {user_id}', StatusCode.EXCEPTION.value)

    return user_id

@app.route('/~rpc/getReviews',  methods=['POST'])
@auth_required
def get_reviews():
    with open('settings.json', 'rb') as PFile:
        settings_url = json.loads(PFile.read().decode('utf-8'))['urlOneVizion']

    REVIEW_JSON_DATA_1 = {'reviewId':{'projectId':'blank','reviewId':Review.SUMMARY_TEST_1.value},
                          'title':f'{Issue.ID_TEST_1.value} {Issue.SUMMARY_TEST_1.value}',
                          'description':f'[{Issue.ID_TEST_1.value}-64]({settings_url}trackor_types/Issue_Task/trackors.do?key={Issue.ID_TEST_1.value}-64) amoiseenko\n \
                                          [{Issue.ID_TEST_1.value}-62]({settings_url}trackor_types/Issue_Task/trackors.do?key={Issue.ID_TEST_1.value}-62) vadim.glebov',
                          'participants':[{'userId':User.ID_TEST_3.value,'role':2,'state':2},
                                          {'userId':User.ID_TEST_1.value,'role':2,'state':2},
                                          {'userId':User.ID_TEST_2.value,'role':2,'state':2},
                                          {'userId':User.ID_TEST_4.value,'role':1,'state':2}],
                          'state':1,'createdBy':User.ID_TEST_3.value}
    REVIEW_JSON_DATA_2 = {'reviewId':{'projectId':'blank','reviewId':Review.SUMMARY_TEST_2.value},
                          'title':f'{Issue.ID_TEST_2.value} {Issue.SUMMARY_TEST_2.value}',
                          'participants':[{'userId':User.ID_TEST_1.value,'role':1,'state':1}],
                          'state':1,'createdBy':User.ID_TEST_3.value}
  

    query = request.get_json()['query']

    if query not in (Issue.ID_TEST_2.value, Issue.ID_TEST_1.value, Review.SUMMARY_TEST_1.value, Review.SUMMARY_TEST_2.value, 'state: open'):
        return make_response(f'Review for {query} not found', StatusCode.EXCEPTION.value)


    if query == Issue.ID_TEST_2.value:
        json_data = {'result': {'hasMore': False, 'totalCount': 0}}
    elif query == Review.SUMMARY_TEST_2.value:
        json_data = {'result':{'reviews':[REVIEW_JSON_DATA_2]}}
    elif query == Issue.ID_TEST_1.value or query == Review.SUMMARY_TEST_1.value:
        json_data = {'result':{'reviews':[REVIEW_JSON_DATA_1]}}
    elif query == 'state: open':
        json_data = {'result':{'reviews':[REVIEW_JSON_DATA_1, REVIEW_JSON_DATA_2]}}
        print(json_data)
    else:
        json_data = {'result': {'hasMore': False, 'totalCount': 0}}

    return json_data

@app.route('/~rpc/renameReview',  methods=['POST'])
@auth_required
def rename_review():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in (Review.SUMMARY_TEST_1.value, Review.SUMMARY_TEST_2.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id

@app.route('/~rpc/createReview',  methods=['POST'])
@auth_required
def create_review():
    revisions = request.get_json()['revisions']

    if revisions == Review.ID_TEST_2.value:
        json_data = {'result':{
                'reviewId':{'projectId':'blank','reviewId':Review.SUMMARY_TEST_2.value},
                'title':f'{Issue.ID_TEST_2.value} {Issue.SUMMARY_TEST_2.value}',
                'participants':[{'userId':User.ID_TEST_3.value,'role':2,'state':1},
                                {'userId':User.ID_TEST_1.value,'role':1,'state':1}],
                'state':1,'createdBy':User.ID_TEST_3.value}}
    elif revisions == Review.ID_TEST_1.value:
        return make_response(f'Cannot create review because revision {revisions} is already in review Review(reviewId=ReviewId[{Review.ID_TEST_1.value}], \
                                title=\'{Issue.ID_TEST_1.value} {Issue.SUMMARY_TEST_1.value}\'', StatusCode.EXCEPTION.value)
    else:
        return make_response(f'Cannot resolve revision {revisions} in project blank', StatusCode.EXCEPTION.value)

    return json_data

@app.route('/~rpc/editReviewDescription',  methods=['POST'])
@auth_required
def update_review_description():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in (Review.SUMMARY_TEST_1.value, Review.SUMMARY_TEST_2.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id


class StatusCode(Enum):
    UNAUTHORIZED = 401
    EXCEPTION = 555


class Review(Enum):
    ID_TEST_1 = '6c3fd124ae40d499e7c27d22381c8a07e8f78afa'
    ID_TEST_2 = '5de06f7e6562b385e707b9beee3c559d1a237184'

    SUMMARY_TEST_1 = 'BLNK-CR-127'
    SUMMARY_TEST_2 = 'BLNK-CR-128'


class Issue(Enum):
    ID_TEST_1 = 'Depl-125306'
    ID_TEST_2 = 'IHub-146144'

    SUMMARY_TEST_1 = 'Configure \'blank\' project in AWS'
    SUMMARY_TEST_2 = 'Test Upsource integration'


class User(Enum):
    ID_TEST_1 = '4006a614-5f72-4c75-a6e7-389e49ccb4fa'
    ID_TEST_2 = 'dfed774e-37c7-49bd-9059-6aa51bad1bb8'
    ID_TEST_3 = '30c91c19-e69f-4de9-92a1-7da68aec71af'
    ID_TEST_4 = '795d4839-3e99-4b76-b35c-e70f80ab856c'

    NAME_TEST_1 = 'asmoiseenko'
    NAME_TEST_2 = 'Vadim'
    NAME_TEST_3 = 'Ilya Emelyanov'


if __name__ == '__main__':
    app.run(debug=True)