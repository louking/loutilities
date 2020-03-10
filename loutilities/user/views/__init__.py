###########################################################################################
# blueprint for this view folder
#
#       Date            Author          Reason
#       ----            ------          ------
#       03/06/20        Lou King        Create
#
#   Copyright 2020 Lou King
###########################################################################################

from flask import Blueprint

bp = Blueprint('userrole', __name__.split('.')[0], url_prefix='/admin', static_folder='static/admin', template_folder='templates/admin')

# import views
from . import userrole
