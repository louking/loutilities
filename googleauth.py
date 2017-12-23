# -*- coding: utf-8 -*-
###########################################################################################
#   googleapi - connect to google api through oauth 2
#
#   Date        Author      Reason
#   ----        ------      ------
#   12/02/27    Lou King    adapted from https://developers.google.com/identity/protocols/OAuth2WebServer
#
#   Copyright 2017 Lou King
###########################################################################################

# standard
import os.path
from traceback import format_exc

#pypi
import flask
from flask.views import View
import requests
import jwt

import google.oauth2.credentials
import google_auth_oauthlib.flow
from  apiclient import discovery
from oauth2client.file import Storage
from oauth2client.client import GoogleCredentials

PLUS_SERVICE = 'plus'
PLUS_VERSION = 'v1'

############################################################################
class GoogleAuth(View):
############################################################################

    #----------------------------------------------------------------------
    def __init__( self, app, client_secrets_file, scopes, startendpoint, credfolder=None, info=None, debug=None ):
    #----------------------------------------------------------------------
        '''
        :param app: flask application
        :param client_secrets_file: client_secrets.json path
        :param scopes: list of google scopes. see https://developers.google.com/identity/protocols/googlescopes
        :param startendpoint: endpoint to start with after authorization completed (no leading slash)
        :param credfolder: folder where credential Storage will be placed
        :param info: info logger function
        :param debug: debug logger function
        '''
        self.app = app
        self.client_secrets_file = client_secrets_file
        self.scopes = scopes
        self.startendpoint = startendpoint
        self.credfolder = credfolder
        self.info = info
        self.debug = debug

    #----------------------------------------------------------------------
    def register(self):
    #----------------------------------------------------------------------
        # create supported endpoints
        self.app.add_url_rule('/authorize', view_func=self.authorize, methods=['GET',])
        # from https://developers.google.com/actions/identity/oauth2-code-flow
        ## 
        # self.app.add_url_rule('/token', view_func=self.token, methods=['POST',])
        self.app.add_url_rule('/oauth2callback', view_func=self.oauth2callback, methods=['GET',])
        # self.app.add_url_rule('/revoke', view_func=self.revoke, methods=['GET',])
        self.app.add_url_rule('/clear', view_func=self.clear_credentials, methods=['GET',])


    #----------------------------------------------------------------------
    def authorize(self):
    #----------------------------------------------------------------------
        # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            self.client_secrets_file, scopes=self.scopes)

        flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

        authorization_url, state = flow.authorization_url(
            # Enable offline access so that you can refresh an access token without
            # re-prompting the user for permission. Recommended for web server apps.
            access_type='offline',
            # Enable incremental authorization. Recommended as a best practice.
            include_granted_scopes='true')

        # Store the state so the callback can verify the auth server response.
        flask.session['state'] = state

        return flask.redirect(authorization_url)

    # #----------------------------------------------------------------------
    # def token(self):
    # #----------------------------------------------------------------------
    #     # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    #     flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    #         self.client_secrets_file, scopes=self.scopes)

    #     # flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

    #     # authorization_url, state = flow.authorization_url(
    #     #     # Enable offline access so that you can refresh an access token without
    #     #     # re-prompting the user for permission. Recommended for web server apps.
    #     #     access_type='offline',
    #     #     # Enable incremental authorization. Recommended as a best practice.
    #     #     include_granted_scopes='true')

    #     # # Store the state so the callback can verify the auth server response.
    #     # flask.session['state'] = state

    #     # return flask.redirect(authorization_url)


    #----------------------------------------------------------------------
    def oauth2callback(self):
    #----------------------------------------------------------------------
        # Specify the state when creating the flow in the callback so that it can
        # verified in the authorization server response.
        state = flask.session['state']
  
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            self.client_secrets_file, scopes=self.scopes, state=state)
        flow.redirect_uri = flask.url_for('oauth2callback', _external=True)
  
        # Use the authorization server's response to fetch the OAuth 2.0 tokens.
        authorization_response = flask.request.url
        token = flow.fetch_token(authorization_response=authorization_response)
        if self.debug: self.debug( 'oauth2callback() token = {}'.format(token) )

        # Store credentials
        # ACTION ITEM: In a production app, you likely want to save these
        #              credentials in a persistent database instead.
        # see https://github.com/GoogleCloudPlatform/google-cloud-python/issues/1412
        # credentials = flow.credentials
        try:
            credentials = GoogleCredentials(
                token['access_token'],
                flow.credentials.client_id,
                flow.credentials.client_secret,
                flow.credentials.refresh_token,
                flow.credentials.expiry,
                flow.credentials.token_uri,
                flask.request.headers['USER_AGENT'],
                # revoke_uri=flow.credentials.revoke_uri, # try default
            )
            user_id = self.get_userid(credentials)
            # user_id = credentials.it_token['sub']
        except AttributeError:
            cause = format_exc()
            if self.debug: self.debug( 'oauth2callback() AttributeError\n{}'.format(cause) )
            credentials = flow.credentials
            user_id = None

        # get information about the user. see https://developers.google.com/identity/toolkit/securetoken
        if self.debug: self.debug( 'oauth2callback() user_id = {}'.format(user_id) )

        # found user_id reference in http://oauth2client.readthedocs.io/en/latest/source/oauth2client.contrib.flask_util.html#module-oauth2client.contrib.flask_util
        if user_id:
            credfile = os.path.join(self.credfolder, user_id)
            storage = Storage(credfile)
            credentials.set_store(storage)
            storage.put(credentials)
            flask.session['user_id'] = user_id
        if self.debug: self.debug( 'oauth2callback() flask.session = {}'.format(flask.session) )

        return flask.redirect(flask.url_for(self.startendpoint))


    # #----------------------------------------------------------------------
    # def revoke(self):
    # #----------------------------------------------------------------------
    #     credentials = get_credentials(self.credfolder)

    #     if credentials:
    #         revoke = requests.post('https://accounts.google.com/o/oauth2/revoke',
    #             params={'token': credentials.token},
    #             headers = {'content-type': 'application/x-www-form-urlencoded'})

    #         status_code = getattr(revoke, 'status_code')
    #         if status_code == 200:
    #             return('Credentials successfully revoked')
    #         else:
    #             return('An error occurred')

    #     else:
    #         return ('You need to <a href="/authorize">authorize</a> before ' +
    #                 'testing the code to revoke credentials')


    #----------------------------------------------------------------------
    def clear_credentials(self):
    #----------------------------------------------------------------------
        if 'credentials' in flask.session:
            del flask.session['credentials']
        if 'user_id' in flask.session:
            del flask.session['user_id']
        return ('Credentials have been cleared')

    # #----------------------------------------------------------------------
    # def get_credentials(self):
    # #----------------------------------------------------------------------
    #     ##@#@# not in use
    #     # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    #     flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
    #         self.client_secrets_file, scopes=self.scopes)
    #     flow.redirect_uri = flask.url_for('oauth2callback', _external=True)
    #     authorization_url, state = flow.authorization_url(
    #         # Enable offline access so that you can refresh an access token without
    #         # re-prompting the user for permission. Recommended for web server apps.
    #         access_type='offline',
    #         # Enable incremental authorization. Recommended as a best practice.
    #         include_granted_scopes='true')

    #     # Store the state so the callback can verify the auth server response.
    #     flask.session['state'] = state

    #     token = flow.fetch_token()        

    #----------------------------------------------------------------------
    def get_userid(self, credentials):
    #----------------------------------------------------------------------
        try:
            user_id = flask.session['user_id']
        
        except KeyError:
            try:
                people = discovery.build(PLUS_SERVICE, PLUS_VERSION, credentials=credentials).people()
                profile = people.get(userId='me').execute()
                user_id = profile['id']
                if self.debug: self.debug( 'get_userid() profile = {}'.format(profile) )
            
            except google.auth.exceptions.RefreshError:
                if self.debug: self.debug( 'invalid grant received when trying to get user profile, continuing' )
                user_id = None

        return user_id

        # # see https://developers.google.com/identity/toolkit/securetoken
        # user_id = None
        # try:
        #     user_data = jwt.decode(token,
        #                            issuer="https://securetoken.google.com",
        #                            audience="running-routes-db-187616")
        #     user_id = user_data["sub"]
        # except jwt.InvalidTokenError:
        #     if self.debug: self.debug( 'get_userid() Invalid token' )
        # except jwt.ExpiredSignatureError:
        #     if self.debug: self.debug( 'get_userid() Token has expired' )
        # except jwt.InvalidIssuerError:
        #     if self.debug: self.debug( 'get_userid() Token is not issued by Google' )
        # except jwt.InvalidAudienceError:
        #     if self.debug: self.debug( 'get_userid() Token is not valid for this endpoint' )

        # return user_id



#----------------------------------------------------------------------
def credentials_to_dict(credentials):
#----------------------------------------------------------------------
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}

#----------------------------------------------------------------------
def get_credentials(credfolder):
#----------------------------------------------------------------------
    try:
        user_id = flask.session['user_id']
        credfile = os.path.join(credfolder, user_id)
        storage = Storage(credfile)
        credentials = storage.get()
        credentials.set_store(storage)
    except KeyError:
        credentials = None

    return credentials

    # if 'credentials' in flask.session:
    #     # https://stackoverflow.com/questions/29154374/how-can-i-refresh-a-stored-google-oauth-credential
    #     credentials = google.oauth2.credentials.Credentials(
    #                             **flask.session['credentials'])
    #     # if credentials.access_token_expired:
    #     #     credentials.refresh(httplib2.Http())
    #     flask.session['credentials'] = credentials_to_dict( credentials )
    #     return credentials
    # else:
    #     return None
