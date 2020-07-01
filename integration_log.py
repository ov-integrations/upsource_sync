import logging
import sys

def log_builder(name=__file__, file='log.txt', encoding='utf-8'):
    log = logging.getLogger(name)
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s] %(filename)s:%(lineno)d %(levelname)-8s %(message)s')
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setFormatter(formatter)
    log.addHandler(sh)
    return log