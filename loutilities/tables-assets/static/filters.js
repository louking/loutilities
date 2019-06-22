// some filters are persistent across pages
// when the page is loaded, the session storage is checked for filter value and if found applied
// if not found in session storage, the local storage is checked for filter value, 
//    and if found applied and value copied to session storage
// if not in local or session storage, no filter is applied
// when filter is changed the value in session storage is changed, if not 'transient' local storage is changed
// local storage is set to 'default' value if present upon registration

var fltr_persistent = {};

// should be called once per page for each persistent filter, before afterdatatables is called
function fltr_register(id, def, transient) {
    // id is id containing filter value
    // def is default value for local storage
    // transient = true means don't update local storage

    // nothing to do if storage not available
    if (typeof(Storage) == "undefined") return;

    // don't add this again
    if (fltr_persistent[id] == undefined) {
        fltr_persistent[id] = JSON.stringify({'transient' : transient, 'val' : def});

        if (transient) {
            localStorage[id] = fltr_persistent[id];
        }
    }
}

// get column number for div surrounding yadcf filter
function get_yadcf_col(id) {
    thisid = $('#'+id+' .yadcf-filter').attr('id');
    idsplit = thisid.split('-');
    col = idsplit[idsplit.length-1];
    return col;
}

// should be called from afterdatatables to set current values and register change triggers
function fltr_init() {
    // nothing to do if storage not available
    if (typeof(Storage) == "undefined") return;

    // initialze storage for each registered id
    for (var id in fltr_persistent) {
        if (fltr_persistent.hasOwnProperty(id)) {
            // get default information
            var defaultobj = JSON.parse(fltr_persistent[id]);

            // if no local storage set, need to initialize filter to default
            if (localStorage[id] == undefined) {
                localStorage[id] = JSON.stringify(defaultobj);
            }
            // if no session storage, initialize from local (note local may have just been initialized from default)
            if (sessionStorage[id] == undefined) {
                localobj = JSON.parse(localStorage[id]);
                sessionStorage[id] = JSON.stringify(localobj);
            }

            // pick up item value from session storage
            var sessionobj = JSON.parse(sessionStorage[id])
            if (sessionobj.val != null) {
                // determine column based on yadcf id
                col = get_yadcf_col(id);
                // set filter
                yadcf.exFilterColumn(_dt_table,[[col, sessionobj.val]])
            }

            // when filter changes, update session storage
            // also update local storage if not transient
            $('#'+id + ' .yadcf-filter').change( function(){
                var id = $( this ).closest('.filter').attr('id');
                col = get_yadcf_col(id);
                var val = yadcf.exGetColumnFilterVal(_dt_table, col);
                sessionobj.val = val
                sessionStorage[id] = JSON.stringify(sessionobj);
                if (!fltr_persistent[id].transient) {
                    var localobj = JSON.parse(localStorage[id])
                    localobj.val = val;
                    localStorage[id] = JSON.stringify(localobj);
                }
            });
        }   // fltr_persistent.hasOwnProperty(id)
    } // for (var id in fltr_persistent)
}

