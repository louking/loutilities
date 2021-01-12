/**
 * use as action button on edit view to reset password, see also user.views.userrole.UserCrudApi
 */

function reset_password_button() {
    this.submit( null, null, function(data){
        data.resetpw = true;
    })
}

/**
 * send reset password notification during create user view, see also user.views.userrole.UserCrudApi
 */
function user_create_send_notification_button() {
    this.submit( null, null, function(data){
        data.resetpw = true;
    })
}