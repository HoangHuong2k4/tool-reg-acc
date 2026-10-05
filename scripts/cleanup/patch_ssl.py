import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
old_request = requests.Session.request

def new_request(*args, **kwargs):
    kwargs['verify'] = False
    return old_request(*args, **kwargs)

requests.Session.request = new_request
