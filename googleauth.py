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
import httplib2

import google.oauth2.credentials
import google_auth_oauthlib.flow
from  apiclient import discovery

# note as of this writing, oauth2client is deprecated. 
# See https://github.com/GoogleCloudPlatform/google-auth-library-python/blob/master/docs/oauth2client-deprecation.rst
# but there is no support in the replacement lib for Storage, and google claims they will maintain without adding features
# so this is probably ok
from oauth2client.file import Storage
from oauth2client.client import GoogleCredentials

PLUS_SERVICE = 'plus'
PLUS_VERSION = 'v1'

############################################################################
class GoogleAuth(View):
############################################################################

    #----------------------------------------------------------------------
    def __init__( self, app, client_secrets_file, scopes, startendpoint, credfolder=None, 
                  logincallback=lambda email: None, logoutcallback=lambda: None,
                  loginfo=None, logdebug=None, logerror=None, ):
    #----------------------------------------------------------------------
        '''
        :param app: flask application
        :param client_secrets_file: client_secrets.json path
        :param scopes: list of google scopes. see https://developers.google.com/identity/protocols/googlescopes
        :param startendpoint: endpoint to start with after authorization completed (no leading slash)
        :param credfolder: folder where credential Storage will be placed
        :param logincallback: function(email) called when login detected
        :param logoutcallback: function called when logout detected
        :param loginfo: info logger function
        :param logdebug: debug logger function
        :param logerror: debug logger function
        '''
        self.app = app
        self.client_secrets_file = client_secrets_file
        self.scopes = scopes
        self.startendpoint = startendpoint
        self.credfolder = credfolder
        self.logincallback = logincallback
        self.logoutcallback = logoutcallback
        self.loginfo = loginfo
        self.logdebug = logdebug
        self.logerror = logerror

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
        if self.logdebug: self.logdebug( 'oauth2callback() token = {}'.format(token) )

        # Store credentials
        ## first convert to GoogleCredentials so these can be saved
        ## see https://github.com/GoogleCloudPlatform/google-cloud-python/issues/1412
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
        except AttributeError:
            cause = format_exc()
            if self.logdebug: self.logdebug( 'oauth2callback() AttributeError\n{}'.format(cause) )
            credentials = flow.credentials
            user_id = None

        if self.logdebug: self.logdebug( 'oauth2callback() user_id = {}'.format(user_id) )

        ## then use user_id to save in credential file
        ## then refresh the credentials
        if user_id:
            credfile = os.path.join(self.credfolder, user_id)
            storage = Storage(credfile)
            # do the new credentials not have a refresh token? do we already have credentials? 
            # if so, just update the access token and expiry from new credentials into stored and resave
            storedcred = storage.get()
            if not credentials.refresh_token and storedcred:
                storedcred.access_token = credentials.access_token
                storedcred.token_expiry = credentials.token_expiry
                credentials = storedcred
            credentials.set_store(storage)
            storage.put(credentials)
            flask.session['user_id'] = user_id
            # refresh
            http = httplib2.Http()
            credentials.refresh(http)

            # take care of login specifics
            self.logincallback(credentials.id_token['email'])

        if self.logdebug: self.logdebug( 'oauth2callback() flask.session = {}'.format(flask.session) )

        return flask.redirect(flask.url_for(self.startendpoint))

    #----------------------------------------------------------------------
    def clear_credentials(self):
    #----------------------------------------------------------------------
        if 'credentials' in flask.session:
            del flask.session['credentials']
        if 'user_id' in flask.session:
            del flask.session['user_id']

        # take care of logout specifics
        self.logoutcallback()

        return 'Credentials have been cleared from session cookie'

    #----------------------------------------------------------------------
    def get_userid(self, credentials):
    #----------------------------------------------------------------------
        try:
            user_id = flask.session['user_id']
            if self.logdebug: self.logdebug( 'get_userid() retrieved user_id from session cookie' )

        except KeyError:
            try:
                people = discovery.build(PLUS_SERVICE, PLUS_VERSION, credentials=credentials).people()
                profile = people.get(userId='me').execute()
                user_id = profile['id']
                if self.logdebug: self.logdebug( 'get_userid() profile from people.get = {}'.format(profile) )
            
            except google.auth.exceptions.RefreshError:
                if self.logdebug: self.logdebug( 'invalid grant received when trying to get user profile, continuing' )
                user_id = None

        return user_id

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
