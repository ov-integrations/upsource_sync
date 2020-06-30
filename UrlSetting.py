import re


class UrlSetting:
    def url_setting(self, url):
        url_re = re.search('upsource', url)
        url_re_start = re.search('^https', url)
        url_re_finish = re.search('/$', url)
        if url_re is None:
            if url_re_start is not None and url_re_finish is not None:
                url_split = re.split('://',url[:-1],2)
                url = url_split[1]  
            elif url_re_start is None and url_re_finish is not None:
                url = url[:-1]
            elif url_re_start is not None and url_re_finish is None:
                url_split = re.split('://',url,2)
                url = url_split[1]
        else:
            if url_re_start is None and url_re_finish is None:
                url = 'https://' + url + '/'
            elif url_re_start is None and url_re_finish is not None:
                url = 'https://' + url
            elif url_re_start is not None and url_re_finish is None:
                url = url + '/'

        return url
