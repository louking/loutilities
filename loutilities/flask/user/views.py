'''
views - flask view support
'''
# standard
from urllib.parse import urlencode

# pypi
from flask import request, redirect, url_for, g, flash

# homegrown
from . import DbCrudApiInterestsRolePermissions

class NotImplementedError(Exception): pass

class SelectInterestsView(DbCrudApiInterestsRolePermissions):
    '''
    create a view with a single select, and a submit button, based on DbCrudApiInterestsRolePermissions for the
    user permissions stuff, otherwise gutted

    :param app: app or blueprint instance
    :param template: (optional) template file to use (defaults to select-view.jinja2)
    :param pagename: page name for title on page
            can also be a function which returns this parameter
    :param endpoint: endpoint parameter used by flask.url_for()
    :param rule: rule parameter used by flask.add_url_rule() [defaults to '/' + endpoint]
    :param displayonly: set to True if the form should only be displayed (no submit option), default False
            can also be a function which returns this parameter
    :param preselecthtml: string any html which needs to go before the select
            can also be a function which returns this parameter
    :param select2options: options for select2 initialization (https://select2.org/configuration/options-api)
            can also be a function which returns this parameter
    '''
    def __init__(self, **kwargs):
        # the args dict has all the defined parameters to
        # caller supplied keyword args are used to update the defaults
        # all arguments are made into attributes for self
        self.kwargs = kwargs
        args = dict(template = 'select-view.jinja2',
                    # pagename = None,
                    # endpoint = None,
                    # rule = None,
                    preselecthtml = '',
                    select2options = {},
                    selectlabel = None,
                    posturl=lambda: self._pageurl(),
                    displayonly=False,
                    )
        args.update(kwargs)

        # expected arguments for DbCrudApiInterestsRolePermissions
        args.update(
            {
                'clientcolumns': [],
            }
        )
        super().__init__(**args)

    def _pageurl(self):
        baseurl = url_for(self.endpoint, interest=g.interest)
        params = urlencode(request.args)
        return '{}?{}'.format(baseurl, params)

    def register(self):
        # name for view is last bit of fully named endpoint
        name = self.endpoint.split('.')[-1]

        # create supported endpoint
        self.my_view = self.as_view(name, **self.kwargs)
        self.app.add_url_rule('{}'.format(self.rule),view_func=self.my_view,methods=['GET', 'POST'])

    # def render_template(self, **kwargs):
    #     return render_template(self.template, **kwargs)

    def getval(self):
        '''
        must be replaced
        :return: value to use for initial val of select
        '''
        raise NotImplementedError

    def putval(self, val):
        '''
        must be replaced
        :param val: value to set based on val of select
        '''
        raise NotImplementedError

    def _template_options(self):
        return dict(
            select2options=self.select2options if not callable(self.select2options) else self.select2options(),
            select2val=self.getval(),
            pagename=self.pagename if not callable(self.pagename) else self.pagename(),
            preselecthtml=self.preselecthtml if not callable(self.preselecthtml) else self.preselecthtml(),
            selectlabel=self.selectlabel if not callable(self.selectlabel) else self.selectlabel(),
            posturl=self.posturl if not callable(self.posturl) else self.posturl(),
            displayonly=self.displayonly if not callable(self.displayonly) else self.displayonly(),
        )

    def get(self):
        if not self.permission():
            self.abort()

        # render page
        return self.render_template(**self._template_options())

    def post(self):
        if not self.permission():
            self.abort()

        val = request.form.get('select-select', None)
        self.putval(val)
        flash('Submission successful')
        return redirect(self._pageurl())

