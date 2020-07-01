from configure_url import configure_url
from datetime import datetime, timedelta
import onevizion


class Issue:
    def __init__(self, url_onevizion, login_onevizion, pass_onevizion, product_onevizion, trackor_type):
        self.url_onevizion = configure_url(url_onevizion)
        self.product_onevizion = product_onevizion
        self.issue_list_request = onevizion.Trackor(trackorType=trackor_type, URL=self.url_onevizion, userName=login_onevizion, password=pass_onevizion)

    def get_list_for_review(self):
        self.issue_list_request.read(
            filters={'Product.TRACKOR_KEY':self.product_onevizion,'VQS_IT_STATUS':'Ready for Review'},
            fields=['TRACKOR_KEY', 'VQS_IT_STATUS', 'VQS_IT_XITOR_NAME']
            )

        return self.issue_list_request.jsonData

    def update_status(self, issue_id, status):
        self.issue_list_request.update(
            trackorId=issue_id,
            fields={'VQS_IT_STATUS':status}
            )

    def update_code_review_url(self, issue_id, url_upsource, project_upsource, review_id):
        self.issue_list_request.update(
            trackorId=issue_id,
            fields={'I_CODE_REVIEW':url_upsource + project_upsource + '/review/' + review_id}
            )

    def get_list_by_title(self, issue_title):
        self.issue_list_request.read(
            filters={'Product.TRACKOR_KEY':self.product_onevizion,'TRACKOR_KEY':issue_title},
            fields=['TRACKOR_KEY', 'VQS_IT_STATUS', 'Version.VER_UAT_DATE']
            )

        return self.issue_list_request.jsonData
