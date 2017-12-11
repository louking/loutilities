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

#pypi
import flask
from flask.views import View
import requests

import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery

############################################################################
class GoogleAuth(View):
############################################################################

    #----------------------------------------------------------------------
    def __init__( self, app, client_secrets_file, scopes, startendpoint ):
    #----------------------------------------------------------------------
        '''
        :param app: flask application
        :param client_secrets_file: client_secrets.json path
        :param scopes: list of google scopes. see https://developers.google.com/identity/protocols/googlescopes
        :param startendpoint: endpoint to start with after authorization completed (no leading slash)
        '''
        self.app = app
        self.client_secrets_file = client_secrets_file
        self.scopes = scopes
        self.startendpoint = startendpoint

    #----------------------------------------------------------------------
    def register(self):
    #----------------------------------------------------------------------
        # create supported endpoints
        self.app.add_url_rule('/authorize',view_func=self.authorize,methods=['GET',])
        self.app.add_url_rule('/oauth2callback',view_func=self.oauth2callback,methods=['GET',])
        self.app.add_url_rule('/revoke',view_func=self.revoke,methods=['GET',])
        self.app.add_url_rule('/clear',view_func=self.clear_credentials,methods=['GET',])


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
        print flask.session

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
      flow.fetch_token(authorization_response=authorization_response)

      # Store credentials in the session.
      # ACTION ITEM: In a production app, you likely want to save these
      #              credentials in a persistent database instead.
      credentials = flow.credentials
      flask.session['credentials'] = credentials_to_dict(credentials)

      return flask.redirect(flask.url_for(self.startendpoint))


    #----------------------------------------------------------------------
    def revoke(self):
    #----------------------------------------------------------------------
        if 'credentials' not in flask.session:
            return ('You need to <a href="/authorize">authorize</a> before ' +
                    'testing the code to revoke credentials')

        credentials = google.oauth2.credentials.Credentials(
                                **flask.session['credentials'])

        revoke = requests.post('https://accounts.google.com/o/oauth2/revoke',
            params={'token': credentials.token},
            headers = {'content-type': 'application/x-www-form-urlencoded'})

        status_code = getattr(revoke, 'status_code')
        if status_code == 200:
            return('Credentials successfully revoked')
        else:
            return('An error occurred')


    #----------------------------------------------------------------------
    def clear_credentials(self):
    #----------------------------------------------------------------------
        if 'credentials' in flask.session:
            del flask.session['credentials']
        return ('Credentials have been cleared')


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
def get_credentials():
#----------------------------------------------------------------------
    if 'credentials' in flask.session:
        return google.oauth2.credentials.Credentials(
                                **flask.session['credentials'])
    else:
        return None