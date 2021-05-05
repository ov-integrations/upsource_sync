from enum import Enum
import json


class StatusCode(Enum):
    UNAUTHORIZED = 401
    EXCEPTION = 555


class Review(Enum):

    def __init__(self, review_id, review_key):
        self.review_id = review_id
        self.review_key = review_key

    BLNK_CR_127 = ('6c3fd124ae40d499e7c27d22381c8a07e8f78afa', 'BLNK-CR-127')
    BLNK_CR_128 = ('5de06f7e6562b385e707b9beee3c559d1a237184', 'BLNK-CR-128')


class Issue(Enum):

    def __init__(self, issue_id, summary):
        self.issue_id = issue_id
        self.summary = summary

    DEPL_125306 = ('Depl-125306', 'Configure \'blank\' project in AWS')
    IHUB_146144 = ('IHub-146144', 'Test Upsource integration')


class User(Enum):

    def __init__(self, user_id, user_name):
        self.user_id = user_id
        self.user_name = user_name

    ASMOISEENKO = ('4006a614-5f72-4c75-a6e7-389e49ccb4fa', 'asmoiseenko')
    VADIM = ('dfed774e-37c7-49bd-9059-6aa51bad1bb8', 'Vadim')
    ILYA_EMELYANOV = ('30c91c19-e69f-4de9-92a1-7da68aec71af', 'Ilya Emelyanov')
    TEST_USER = ('795d4839-3e99-4b76-b35c-e70f80ab856c', '')

BLNK_CR_127_REVIEW_JSON_DATA = {'reviewId':{'projectId':'blank','reviewId':Review.BLNK_CR_127.review_key},
                                'title':f'{Issue.DEPL_125306.issue_id} {Issue.DEPL_125306.summary}',
                                'description':f'[{Issue.DEPL_125306.issue_id}-64](settings_url/trackor_types/Issue_Task/trackors.do?key={Issue.DEPL_125306.issue_id}-64) amoiseenko\n \
                                                [{Issue.DEPL_125306.issue_id}-62](settings_url/trackor_types/Issue_Task/trackors.do?key={Issue.DEPL_125306.issue_id}-62) vadim.glebov',
                                'participants':[{'userId':User.ILYA_EMELYANOV.user_id,'role':2,'state':2},
                                                {'userId':User.ASMOISEENKO.user_id,'role':2,'state':2},
                                                {'userId':User.VADIM.user_id,'role':2,'state':2},
                                                {'userId':User.TEST_USER.user_id,'role':1,'state':2}],
                                'state':1,'createdBy':User.ILYA_EMELYANOV.user_id}
BLNK_CR_128_REVIEW_JSON_DATA = {'reviewId':{'projectId':'blank','reviewId':Review.BLNK_CR_128.review_key},
                                'title':f'{Issue.IHUB_146144.issue_id} {Issue.IHUB_146144.summary}',
                                'participants':[{'userId':User.ASMOISEENKO.user_id,'role':1,'state':1}],
                                'state':1,'createdBy':User.ILYA_EMELYANOV.user_id}
SUPPORTED_REVIEWS = (Review.BLNK_CR_127.review_key, Review.BLNK_CR_128.review_key)
SUPPORTED_USERS = (User.ASMOISEENKO.user_id, User.VADIM.user_id, User.ILYA_EMELYANOV.user_id)