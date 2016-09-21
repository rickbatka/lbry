import urlparse
import logging
import requests
import os
import base64
import json

from lbrynet.lbrynet_daemon.auth.util import load_api_keys, APIKey, API_KEY_NAME
from lbrynet.conf import API_INTERFACE, API_ADDRESS, API_PORT
from lbrynet.conf import DATA_DIR

log = logging.getLogger(__name__)
USER_AGENT = "AuthServiceProxy/0.1"
TWISTED_SESSION = "TWISTED_SESSION"
LBRY_SECRET = "LBRY_SECRET"
HTTP_TIMEOUT = 30


class JSONRPCException(Exception):
    def __init__(self, rpc_error):
        Exception.__init__(self)
        self.error = rpc_error


class LBRYAPIClient(object):
    def __init__(self, key, timeout, connection, count, service, cookies, auth, url, login_url):
        self.__service_name = service
        self.__api_key = key
        self.__service_url = login_url
        self.__id_count = count
        self.__url = url
        self.__auth_header = auth
        self.__conn = connection
        self.__cookies = cookies

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            # Python internal stuff
            raise AttributeError
        if self.__service_name is not None:
            name = "%s.%s" % (self.__service_name, name)
        return LBRYAPIClient(key=self.__api_key,
                             timeout=HTTP_TIMEOUT,
                             connection=self.__conn,
                             count=self.__id_count,
                             service=name,
                             cookies=self.__cookies,
                             auth=self.__auth_header,
                             url=self.__url,
                             login_url=self.__service_url)

    def __call__(self, *args):
        self.__id_count += 1
        pre_auth_postdata = {'version': '1.1',
                             'method': self.__service_name,
                             'params': args,
                             'id': self.__id_count}
        to_auth = str(pre_auth_postdata['method']).encode('hex') + str(pre_auth_postdata['id']).encode('hex')
        token = self.__api_key.get_hmac(to_auth.decode('hex'))
        pre_auth_postdata.update({'hmac': token})
        postdata = json.dumps(pre_auth_postdata)
        service_url = self.__service_url
        auth_header = self.__auth_header
        cookies = self.__cookies
        host = self.__url.hostname

        req = requests.Request(method='POST',
                               url=service_url,
                               data=postdata,
                               headers={'Host': host,
                                        'User-Agent': USER_AGENT,
                                        'Authorization': auth_header,
                                        'Content-type': 'application/json'},
                               cookies=cookies)
        r = req.prepare()
        http_response = self.__conn.send(r)
        cookies = http_response.cookies
        headers = http_response.headers
        next_secret = headers.get(LBRY_SECRET, False)

        if next_secret:
            # print "Next secret: %s" % next_secret
            self.__api_key.secret = next_secret
            self.__cookies = cookies

        # print "Postdata: %s" % postdata
        if http_response is None:
            raise JSONRPCException({
                'code': -342, 'message': 'missing HTTP response from server'})

        # print "-----\n%s\n------" % http_response.text
        http_response.raise_for_status()

        response = http_response.json()

        if response['error'] is not None:
            raise JSONRPCException(response['error'])
        elif 'result' not in response:
            raise JSONRPCException({
                'code': -343, 'message': 'missing JSON-RPC result'})
        else:
            return response['result']

    @classmethod
    def config(cls, key_name=None, key=None, pw_path=None, timeout=HTTP_TIMEOUT, connection=None, count=0,
                                            service=None, cookies=None, auth=None, url=None, login_url=None):
        api_key_name = API_KEY_NAME if not key_name else key_name
        pw_path = os.path.join(DATA_DIR, ".api_keys") if not pw_path else pw_path

        if not key:
            keys = load_api_keys(pw_path)
            api_key = keys.get(api_key_name, False)
        else:
            api_key = APIKey(name=api_key_name, secret=key)

        if login_url is None:
            service_url = "http://%s:%s@%s:%i/%s" % (api_key_name, api_key.secret, API_INTERFACE, API_PORT, API_ADDRESS)
        else:
            service_url = login_url

        id_count = count

        if auth is None and connection is None and cookies is None and url is None:
            # This is a new client instance, initialize the auth header and start a session
            url = urlparse.urlparse(service_url)
            (user, passwd) = (url.username, url.password)
            try:
                user = user.encode('utf8')
            except AttributeError:
                pass
            try:
                passwd = passwd.encode('utf8')
            except AttributeError:
                pass
            authpair = user + b':' + passwd
            auth_header = b'Basic ' + base64.b64encode(authpair)

            conn = requests.Session()
            conn.auth = (user, passwd)

            req = requests.Request(method='POST',
                                   url=service_url,
                                   auth=conn.auth,
                                   headers={'Host': url.hostname,
                                            'User-Agent': USER_AGENT,
                                            'Authorization': auth_header,
                                            'Content-type': 'application/json'},)
            r = req.prepare()
            http_response = conn.send(r)
            cookies = http_response.cookies
            # print "Logged in"

            uid = cookies.get(TWISTED_SESSION)
            api_key = APIKey.new(seed=uid)
            # print "Created temporary api key"
        else:
            # This is a client that already has a session, use it
            auth_header = auth
            conn = connection
            assert cookies.get(LBRY_SECRET, False), "Missing cookie"
            secret = cookies.get(LBRY_SECRET)
            api_key = APIKey(secret, api_key_name)
        return cls(api_key, timeout, conn, id_count, service, cookies, auth_header, url, service_url)