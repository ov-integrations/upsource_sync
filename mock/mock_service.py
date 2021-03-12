from re import A
from flask import Flask, request, make_response
from flask_wtf import CSRFProtect
from functools import wraps
from enum import Enum

import json


app = Flask(__name__)
csrf = CSRFProtect()
csrf.init_app(app)

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
@csrf.exempt
@auth_required
def main():
    return 'You are logged in'

@app.route('/~rpc/getRevisionsListFiltered',  methods=['POST'])
@csrf.exempt
@auth_required
def get_filtered_revision_list():
    query = request.get_json()['query']

    if query not in (IssueData.ID_TWO.value, IssueData.ID_ONE.value):
        return make_response(f'Revision for {query} not found', StatusCode.EXCEPTION.value)

    if query == IssueData.ID_TWO.value:
        json_data = {'result': {'revision': [{'revisionId': ReviewData.ID_TWO.value, 
                'revisionCommitMessage': f'{IssueData.ID_TWO.value} {IssueData.NAME_TWO.value}\n'}]}}
    elif query == IssueData.ID_ONE.value:
        json_data = {'result': {'revision': [{'revisionId': ReviewData.ID_ONE.value, 
                'revisionCommitMessage': f'{IssueData.ID_ONE.value} {IssueData.NAME_ONE.value}\n'}]}}
    else:
        json_data = {'result': {'query': f'{query}'}}

    return json_data

@app.route('/~rpc/closeReview',  methods=['POST'])
@csrf.exempt
@auth_required
def close_review():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in (ReviewData.NAME_ONE.value, ReviewData.NAME_TWO.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id

@app.route('/~rpc/getBranches',  methods=['POST'])
@csrf.exempt
@auth_required
def get_branch():
    query = request.get_json()['query']

    if query == IssueData.ID_TWO.value:
        json_data =  {'result': {'defaultBranch': 'master'}}
    elif query == IssueData.ID_ONE.value:
        json_data = {'result': {'branch': [{'name': IssueData.ID_TWO.value}]}}
    else:
        return make_response(f'Branch {query} not found', StatusCode.EXCEPTION.value)

    return json_data

@app.route('/~rpc/startBranchTracking',  methods=['POST'])
@csrf.exempt
@auth_required
def start_branch_tracking():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in (ReviewData.NAME_ONE.value, ReviewData.NAME_TWO.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id

@app.route('/~rpc/findUsers',  methods=['POST'])
@csrf.exempt
@auth_required
def find_users():
    pattern = request.get_json()['pattern']

    if pattern == UserData.NAME_ONE.value:
        json_data = {'result': {'infos': [{'userId': UserData.ID_ONE.value}]}}
    elif pattern == UserData.NAME_TWO.value:
        json_data = {'result': {'infos': [{'userId': UserData.ID_TWO.value}]}}
    elif pattern == UserData.NAME_THREE.value:
        json_data = {'result': {'infos': [{'userId': UserData.ID_THREE.value}]}}
    else:
        return make_response(f'Cannot resolve pattern {pattern}', StatusCode.EXCEPTION.value)

    return json_data

@app.route('/~rpc/updateParticipantInReview',  methods=['POST'])
@csrf.exempt
@auth_required
def update_participant_status():
    review_id = request.get_json()['reviewId']['reviewId']
    user_id = request.get_json()['userId']

    if review_id not in (ReviewData.NAME_ONE.value, ReviewData.NAME_TWO.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    if user_id not in (UserData.ID_ONE.value, UserData.ID_TWO.value, UserData.ID_THREE.value):
        return make_response(f'Cannot resolve user id {user_id}', StatusCode.EXCEPTION.value)

    return user_id

@app.route('/~rpc/addParticipantToReview',  methods=['POST'])
@csrf.exempt
@auth_required
def add_reviewer():
    review_id = request.get_json()['reviewId']['reviewId']
    user_id = request.get_json()['participant']['userId']

    if review_id not in (ReviewData.NAME_ONE.value, ReviewData.NAME_TWO.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    if user_id not in (UserData.ID_ONE.value, UserData.ID_TWO.value, UserData.ID_THREE.value):
        return make_response(f'Cannot resolve user id {user_id}', StatusCode.EXCEPTION.value)

    return user_id

@app.route('/~rpc/removeParticipantFromReview',  methods=['POST'])
@csrf.exempt
@auth_required
def remove_reviewer():
    review_id = request.get_json()['reviewId']['reviewId']
    user_id = request.get_json()['participant']['userId']

    if review_id not in (ReviewData.NAME_ONE.value, ReviewData.NAME_TWO.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    if user_id not in (UserData.ID_ONE.value, UserData.ID_TWO.value, UserData.ID_THREE.value):
        return make_response(f'Cannot resolve user id {user_id}', StatusCode.EXCEPTION.value)

    return user_id

@app.route('/~rpc/getReviews',  methods=['POST'])
@csrf.exempt
@auth_required
def get_reviews():
    query = request.get_json()['query']

    if query not in (IssueData.ID_TWO.value, IssueData.ID_ONE.value, ReviewData.NAME_ONE.value, ReviewData.NAME_TWO.value, 'state: open'):
        return make_response(f'Review for {query} not found', StatusCode.EXCEPTION.value)

    with open('settings.json', 'rb') as PFile:
        settings_url = json.loads(PFile.read().decode('utf-8'))['urlOneVizion']

    if query == IssueData.ID_TWO.value:
        json_data = {'result': {'hasMore': False, 'totalCount': 0}}
    elif query == ReviewData.NAME_TWO.value:
        json_data = {'result':{'reviews':[{
                'reviewId':{'projectId':'blank','reviewId':ReviewData.NAME_TWO.value},
                'title':f'{IssueData.ID_TWO.value} {IssueData.NAME_TWO.value}',
                'participants':[{'userId':UserData.ID_ONE.value,'role':1,'state':1}],
                'state':1,'createdBy':UserData.ID_THREE.value}]}}
    elif query == IssueData.ID_ONE.value or query == ReviewData.NAME_ONE.value:
        json_data = {'result':{'reviews':[{
                'reviewId':{'projectId':'blank','reviewId':ReviewData.NAME_ONE.value},
                'title':f'{IssueData.ID_ONE.value} {IssueData.NAME_ONE.value}',
                'description':f'[{IssueData.ID_ONE.value}-64]({settings_url}trackor_types/Issue_Task/trackors.do?key={IssueData.ID_ONE.value}-64) amoiseenko\n \
                               [{IssueData.ID_ONE.value}-62]({settings_url}trackor_types/Issue_Task/trackors.do?key={IssueData.ID_ONE.value}-62) vadim.glebov',
                'participants':[{'userId':UserData.ID_THREE.value,'role':2,'state':2},
                                {'userId':UserData.ID_ONE.value,'role':2,'state':2},
                                {'userId':UserData.ID_TWO.value,'role':2,'state':2},
                                {'userId':UserData.ID_FOUR.value,'role':1,'state':2}],
                'state':1,'createdBy':UserData.ID_THREE.value}]}}
    elif query == 'state: open':
        json_data = {'result':{'reviews':[{
                'reviewId':{'projectId':'blank','reviewId':ReviewData.NAME_ONE.value},
                'title':f'{IssueData.ID_ONE.value} {IssueData.NAME_ONE.value}',
                'description':f'[{IssueData.ID_ONE.value}-64]({settings_url}trackor_types/Issue_Task/trackors.do?key={IssueData.ID_ONE.value}-64) amoiseenko\n \
                               [{IssueData.ID_ONE.value}-62]({settings_url}trackor_types/Issue_Task/trackors.do?key={IssueData.ID_ONE.value}-62) vadim.glebov',
                'participants':[{'userId':UserData.ID_THREE.value,'role':2,'state':2},
                                {'userId':UserData.ID_ONE.value,'role':2,'state':2},
                                {'userId':UserData.ID_TWO.value,'role':2,'state':2},
                                {'userId':UserData.ID_FOUR.value,'role':1,'state':2}],
                'state':1,'createdBy':UserData.ID_THREE.value},
                {'reviewId':{'projectId':'blank','reviewId':ReviewData.NAME_TWO.value},
                'title':f'{IssueData.ID_TWO.value} {IssueData.NAME_TWO.value}',
                'participants':[{'userId':UserData.ID_ONE.value,'role':1,'state':1}],
                'state':1,'createdBy':UserData.ID_THREE.value}]}}
    else:
        json_data = {'result': {'hasMore': False, 'totalCount': 0}}

    return json_data

@app.route('/~rpc/renameReview',  methods=['POST'])
@csrf.exempt
@auth_required
def rename_review():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in (ReviewData.NAME_ONE.value, ReviewData.NAME_TWO.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id

@app.route('/~rpc/createReview',  methods=['POST'])
@csrf.exempt
@auth_required
def create_review():
    revisions = request.get_json()['revisions']

    if revisions == ReviewData.ID_TWO.value:
        json_data = {'result':{
                'reviewId':{'projectId':'blank','reviewId':ReviewData.NAME_TWO.value},
                'title':f'{IssueData.ID_TWO.value} {IssueData.NAME_TWO.value}',
                'participants':[{'userId':UserData.ID_THREE.value,'role':2,'state':1},
                                {'userId':UserData.ID_ONE.value,'role':1,'state':1}],
                'state':1,'createdBy':UserData.ID_THREE.value}}
    elif revisions == ReviewData.ID_ONE.value:
        return make_response(f'Cannot create review because revision {revisions} is already in review Review(reviewId=ReviewId[{ReviewData.ID_ONE.value}], \
                                title=\'{IssueData.ID_ONE.value} {IssueData.NAME_ONE.value}\'', StatusCode.EXCEPTION.value)
    else:
        return make_response(f'Cannot resolve revision {revisions} in project blank', StatusCode.EXCEPTION.value)

    return json_data

@app.route('/~rpc/editReviewDescription',  methods=['POST'])
@csrf.exempt
@auth_required
def update_review_description():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in (ReviewData.NAME_ONE.value, ReviewData.NAME_TWO.value):
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id


class StatusCode(Enum):
    UNAUTHORIZED = 401
    EXCEPTION = 555


class ReviewData(Enum):
    ID_ONE = '6c3fd124ae40d499e7c27d22381c8a07e8f78afa'
    ID_TWO = '5de06f7e6562b385e707b9beee3c559d1a237184'

    NAME_ONE = 'BLNK-CR-127'
    NAME_TWO = 'BLNK-CR-128'


class IssueData(Enum):
    ID_ONE = 'Depl-125306'
    ID_TWO = 'IHub-146144'

    NAME_ONE = 'Configure \'blank\' project in AWS'
    NAME_TWO = 'Test Upsource integration'


class UserData(Enum):
    ID_ONE = '4006a614-5f72-4c75-a6e7-389e49ccb4fa'
    ID_TWO = 'dfed774e-37c7-49bd-9059-6aa51bad1bb8'
    ID_THREE = '30c91c19-e69f-4de9-92a1-7da68aec71af'
    ID_FOUR = '795d4839-3e99-4b76-b35c-e70f80ab856c'

    NAME_ONE = 'asmoiseenko'
    NAME_TWO = 'Vadim'
    NAME_THREE = 'Ilya Emelyanov'


if __name__ == '__main__':
    app.run(debug=True)