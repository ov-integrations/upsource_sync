from flask import Flask, request, make_response
from flask_httpauth import HTTPTokenAuth
from constants import *
import json
import re


app = Flask(__name__)
with open('settings.json', "rb") as PFile:
    password_data = json.loads(PFile.read().decode('utf-8'))

app.config['SECRET_KEY'] = password_data['tokenUpsource']
auth = HTTPTokenAuth('Bearer')

@auth.verify_token
def verify_token(token):
    if token == app.config['SECRET_KEY']:
        return token

@app.route('/~rpc/getRevisionsListFiltered',  methods=['POST'])
@auth.login_required
def get_filtered_revision_list():
    query = request.get_json()['query']

    if query not in (Issue.IHUB_146144.issue_id, Issue.DEPL_125306.issue_id):
        return make_response(f'Revision for {query} not found', StatusCode.EXCEPTION.value)

    if query == Issue.IHUB_146144.issue_id:
        json_data = {'result': {'revision': [{'revisionId': Review.BLNK_CR_128.review_id, 
                'revisionCommitMessage': f'{Issue.IHUB_146144.issue_id} {Issue.IHUB_146144.summary}\n'}]}}
    elif query == Issue.DEPL_125306.issue_id:
        json_data = {'result': {'revision': [{'revisionId': Review.BLNK_CR_127.review_id, 
                'revisionCommitMessage': f'{Issue.DEPL_125306.issue_id} {Issue.DEPL_125306.summary}\n'}]}}
    else:
        json_data = {'result': {'query': f'{query}'}}

    return json_data

@app.route('/~rpc/closeReview',  methods=['POST'])
@auth.login_required
def close_review():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in SUPPORTED_REVIEWS:
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id

@app.route('/~rpc/getBranches',  methods=['POST'])
@auth.login_required
def get_branch():
    query = request.get_json()['query']

    if query == Issue.IHUB_146144.issue_id:
        json_data =  {'result': {'defaultBranch': 'master'}}
    elif query == Issue.DEPL_125306.issue_id:
        json_data = {'result': {'branch': [{'name': Issue.DEPL_125306.issue_id}]}}
    else:
        return make_response(f'Branch {query} not found', StatusCode.EXCEPTION.value)

    return json_data

@app.route('/~rpc/startBranchTracking',  methods=['POST'])
@auth.login_required
def start_branch_tracking():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in SUPPORTED_REVIEWS:
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id

@app.route('/~rpc/findUsers',  methods=['POST'])
@auth.login_required
def find_users():
    pattern = request.get_json()['pattern']

    if pattern == User.ASMOISEENKO.user_name:
        json_data = {'result': {'infos': [{'userId': User.ASMOISEENKO.user_id}]}}
    elif pattern == User.VADIM.user_name:
        json_data = {'result': {'infos': [{'userId': User.VADIM.user_id}]}}
    elif pattern == User.ILYA_EMELYANOV.user_name:
        json_data = {'result': {'infos': [{'userId': User.ILYA_EMELYANOV.user_id}]}}
    else:
        return make_response(f'Cannot resolve pattern {pattern}', StatusCode.EXCEPTION.value)

    return json_data

@app.route('/~rpc/updateParticipantInReview',  methods=['POST'])
@auth.login_required
def update_participant_status():
    review_id = request.get_json()['reviewId']['reviewId']
    user_id = request.get_json()['userId']

    if review_id not in SUPPORTED_REVIEWS:
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    if user_id not in SUPPORTED_USERS:
        return make_response(f'Cannot resolve user id {user_id}', StatusCode.EXCEPTION.value)

    return user_id

@app.route('/~rpc/addParticipantToReview',  methods=['POST'])
@auth.login_required
def add_reviewer():
    review_id = request.get_json()['reviewId']['reviewId']
    user_id = request.get_json()['participant']['userId']

    if review_id not in SUPPORTED_REVIEWS:
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    if user_id not in SUPPORTED_USERS:
        return make_response(f'Cannot resolve user id {user_id}', StatusCode.EXCEPTION.value)

    return user_id

@app.route('/~rpc/removeParticipantFromReview',  methods=['POST'])
@auth.login_required
def remove_reviewer():
    review_id = request.get_json()['reviewId']['reviewId']
    user_id = request.get_json()['participant']['userId']

    if review_id not in SUPPORTED_REVIEWS:
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    if user_id not in SUPPORTED_USERS:
        return make_response(f'Cannot resolve user id {user_id}', StatusCode.EXCEPTION.value)

    return user_id

@app.route('/~rpc/getReviews',  methods=['POST'])
@auth.login_required
def get_reviews():
    query = request.get_json()['query']

    if query not in (Issue.IHUB_146144.issue_id, Issue.DEPL_125306.issue_id, Review.BLNK_CR_127.review_key, Review.BLNK_CR_128.review_key, 'state: open'):
        return make_response(f'Review for {query} not found', StatusCode.EXCEPTION.value)

    with open('settings.json', 'rb') as PFile:
        settings_url = json.loads(PFile.read().decode('utf-8'))['urlOneVizion']
    blnk_cr_127_review_json_data = json.loads(re.sub('settings_url/', settings_url, json.dumps(BLNK_CR_127_REVIEW_JSON_DATA)))
    

    if query == Issue.IHUB_146144.issue_id:
        json_data = {'result': {'hasMore': False, 'totalCount': 0}}
    elif query == Review.BLNK_CR_128.review_key:
        json_data = {'result':{'reviews':[BLNK_CR_128_REVIEW_JSON_DATA]}}
    elif query in (Issue.DEPL_125306.issue_id, Review.BLNK_CR_127.review_key):
        json_data = {'result':{'reviews':[blnk_cr_127_review_json_data]}}
    elif query == 'state: open':
        json_data = {'result':{'reviews':[blnk_cr_127_review_json_data, BLNK_CR_128_REVIEW_JSON_DATA]}}
    else:
        json_data = {'result': {'hasMore': False, 'totalCount': 0}}

    return json_data

@app.route('/~rpc/renameReview',  methods=['POST'])
@auth.login_required
def rename_review():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in SUPPORTED_REVIEWS:
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id

@app.route('/~rpc/createReview',  methods=['POST'])
@auth.login_required
def create_review():
    revisions = request.get_json()['revisions']

    if revisions == Review.BLNK_CR_128.review_id:
        json_data = {'result':{'reviews':[BLNK_CR_128_REVIEW_JSON_DATA]}}
    elif revisions == Review.BLNK_CR_127.review_id:
        return make_response(f'Cannot create review because revision {revisions} is already in review Review(reviewId=ReviewId[{Review.BLNK_CR_127.review_id}], \
                                title=\'{Issue.DEPL_125306.issue_id} {Issue.DEPL_125306.summary}\'', StatusCode.EXCEPTION.value)
    else:
        return make_response(f'Cannot resolve revision {revisions} in project blank', StatusCode.EXCEPTION.value)

    return json_data

@app.route('/~rpc/editReviewDescription',  methods=['POST'])
@auth.login_required
def update_review_description():
    review_id = request.get_json()['reviewId']['reviewId']

    if review_id not in SUPPORTED_REVIEWS:
        return make_response(f'Review {review_id} not found', StatusCode.EXCEPTION.value)

    return review_id


if __name__ == '__main__':
    app.run(debug=True)