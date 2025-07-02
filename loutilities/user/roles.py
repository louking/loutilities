###########################################################################################
# roles - common location for xtility role declaration
#
#       Date            Author          Reason
#       ----            ------          ------
#       03/11/20        Lou King        Create
#
#   Copyright 2020 Lou King.  All rights reserved
###########################################################################################

from loutilities.user.model import APP_CONTRACTS, APP_MEMBERS, APP_ROUTES, APP_SCORES, APP_ALL

# common roles
ROLE_SUPER_ADMIN = 'super-admin'
ROLES_COMMON = [ROLE_SUPER_ADMIN]
roles_common = [
    {'name': 'super-admin', 'description': 'allowed to do everything on all applications', 'apps': APP_ALL},
]

# members roles
ROLE_LEADERSHIP_ADMIN = 'leadership-admin'
ROLE_LEADERSHIP_MEMBER = 'leadership-member'
ROLE_MEMBERSHIP_ADMIN = 'membership-admin'
ROLE_MEETINGS_ADMIN = 'meetings-admin'
ROLE_MEETINGS_MEMBER = 'meetings-member'
ROLE_RACINGTEAM_ADMIN = 'racingteam-admin'
ROLE_RACINGTEAM_MEMBER = 'racingteam-member'
ROLE_AWARDS_ADMIN = 'awards-admin'
roles_members = [
    {'name': ROLE_LEADERSHIP_ADMIN, 'description': 'access to leadership tasks for members application', 'apps':[APP_MEMBERS]},
    {'name': ROLE_LEADERSHIP_MEMBER, 'description': 'user of leadership tasks for members application', 'apps':[APP_MEMBERS]},
    {'name': ROLE_MEMBERSHIP_ADMIN, 'description': 'access to membership admininstration for members application', 'apps':[APP_MEMBERS]},
    {'name': ROLE_MEETINGS_ADMIN, 'description': 'access to meetings administration for members application', 'apps':[APP_MEMBERS]},
    {'name': ROLE_MEETINGS_MEMBER, 'description': 'user of meetings for members application', 'apps':[APP_MEMBERS]},
    {'name': ROLE_RACINGTEAM_ADMIN, 'description': 'access to racingteam administration for members application', 'apps':[APP_MEMBERS]},
    {'name': ROLE_RACINGTEAM_MEMBER, 'description': 'user of racingteam module for members application', 'apps':[APP_MEMBERS]},
    {'name': ROLE_AWARDS_ADMIN, 'description': 'access to awards administration for members application', 'apps':[APP_MEMBERS]},
]

# routes roles
ROLE_ROUTES_ADMIN = 'routes-admin'
ROLE_ICON_ADMIN = 'icon-admin'
roles_routes = [{'name': ROLE_ROUTES_ADMIN, 'description': 'access to routes for routes application', 'apps':[APP_ROUTES]},
                 {'name': ROLE_ICON_ADMIN, 'description': 'access to icons for routes application', 'apps':[APP_ROUTES]}
                 ]

# contracts roles
ROLE_EVENT_ADMIN = 'event-admin'
ROLE_SPONSOR_ADMIN = 'sponsor-admin'
roles_contracts = [{'name': ROLE_EVENT_ADMIN, 'description': 'access to events for contracts application', 'apps':[APP_CONTRACTS]},
                   {'name': ROLE_SPONSOR_ADMIN, 'description': 'access to sponsors/races for contracts application', 'apps':[APP_CONTRACTS]}
                   ]

# scores roles
ROLE_SCORES_ADMIN = 'scores-admin'
ROLE_SCORES_VIEWER = 'scores-viewer'
roles_scores = [{'name': ROLE_SCORES_ADMIN, 'description': 'administer scores application', 'apps':[APP_SCORES]},
                   {'name': ROLE_SCORES_VIEWER, 'description': 'view scores application', 'apps':[APP_SCORES]},
                   ]

all_roles = [roles_common, roles_contracts, roles_members, roles_routes, roles_scores]