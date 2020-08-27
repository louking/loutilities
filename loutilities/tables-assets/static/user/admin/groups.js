function translate_editor_group(e, data, action) {
    // group comes from external source
    var group = $( this.groups_groupselectselector ).val();
    // save editor's ajax config in this editor's state
    // note use of lodash
    this.groups_staticconfig = _.cloneDeep(this.ajax());
    var newconfig = _.cloneDeep(this.groups_staticconfig);
    // substitute group into urls
    for (const action in newconfig) {
        newconfig[action].url = _.replace(decodeURIComponent(newconfig[action].url), _.replace('<{groupname}>', '{groupname}', this.groups_groupname), group);

        // split out query parameters, and collect in object
        var urlsplit = newconfig[action].url.split('?');
        var urlparams = allUrlParams();

        // skip path. This allows for somewhat embarrassing case of multiple ? in the string
        // note these override original url parameters
        for (var i=1; i<urlsplit.length; i++) {
            var params = deparam(urlsplit[i]);
            $.extend(urlparams, params);
        }

        // tack on url query parameters
        newconfig[action].url = urlsplit[0] + '?' + setParams(urlparams);
    }
    this.ajax(newconfig);
}
function restore_editor_group(e, data, action, xhr) {
    this.ajax(this.groups_staticconfig);
}
function set_editor_event_handlers(ed) {
    // need on 'preEditRefresh' to translate interest for editRefresh editChildRowRefresh buttons
    ed.on( 'preEditRefresh preEditChildRowRefresh', translate_editor_group);
    // need on 'preSubmit' to translate interest for resubmission of form, e.g., after error occurs
    ed.on( 'preSubmit', translate_editor_group);
    // need on 'open' to translate interest for file uploads, as there's no 'preSubmit' for these
    ed.on( 'open', translate_editor_group);

    // return ajax config to what was there before
    ed.on( 'postSubmit', restore_editor_group);

}

function register_group_for_editor(groupname, groupselectselector, ed) {
    // requires Editor
    // expects editor to be set up globally, as in loutilities/table-assets/static/datatables.js
    // call after datatables is initialized

    // backwards compatibility
    if (ed == undefined) {
        ed = editor;
    }

    // use editor class to save some groupselectselector (used by translate_editor_group)
    ed.groups_groupselectselector = groupselectselector
    ed.groups_groupname = groupname
    set_editor_event_handlers(ed);
}

// gives access to url from within url function inside of translate_datatable_group()
var dt_url_hooks = [];
/**
 * add a hook which is called from anonymous function within translate_datatable_group()
 *
 * @param fn - function fn is passed url and returns possibly updated url, i.e., newurl = fn(url)
 */
function dt_add_url_hook(fn) {
    dt_url_hooks.push(fn);
}

var dt_groupname = null;
var dt_groupselectselector = null;
var dt_lastjson = null;
function register_group_for_datatable(groupname, groupselectselector) {
    // the group and groupselector are common for the page, so ok to save globally
    dt_groupselectselector = groupselectselector
    dt_groupname = groupname
}
// this function returns function configured to dataTables ajax parameter, based in indicated url
function translate_datatable_group(url) {
    return function(data, callback, settings) {
        // if no group configured, just use url
        var ajaxurl;
        if (dt_groupname == null) {
            ajaxurl = url;
        } else {
            // group comes from external source
            var group = $( dt_groupselectselector ).val();
            // replace <group> items with current group
            // note use of lodash _.replace
            ajaxurl = _.replace(decodeURIComponent(url), _.replace('<{groupname}>', '{groupname}', dt_groupname), group);
        }

        // tack on current url query parameters
        ajaxurl += '?' + setParams(allUrlParams());

        // apply url hooks
        for (var i=0; i<dt_url_hooks.length; i++) {
            var fn = dt_url_hooks[i];
            ajaxurl = fn(ajaxurl);
        }

        // WARNING: nonstandard/nonpublic use of settings information
        var dt = settings.oApi;

        // adapted from jquery.dataTables.js _fnBuildAjax; _fn functions are from dataTables
        $.ajax({
            "url": ajaxurl,
            "data": data,
            "success": function(json, textStatus, xhr) {
                dt_lastjson = json;
                callback(json)
            },
			"dataType": "json",
			"cache": false,
			"method": 'GET',
			"error": function (xhr, error, thrown) {
				var ret = dt._fnCallbackFire( settings, null, 'xhr', [settings, null, settings.jqXHR] );

				if ( $.inArray( true, ret ) === -1 ) {
					if ( error == "parsererror" ) {
						dt._fnLog( settings, 0, 'Invalid JSON response', 1 );
					}
					else if ( xhr.readyState === 4 ) {
						dt._fnLog( settings, 0, 'Ajax error', 7 );
					}
				}

				dt._fnProcessingDisplay( settings, false );
			}
        });
    }
}

// see https://stackoverflow.com/a/18660968/799921
function link_is_external(link_element) {
    return (link_element.host !== window.location.host);
}

// see https://stackoverflow.com/a/5713807/799921
function deparam(query){
  var setValue = function(root, path, value){
    if(path.length > 1){
      var dir = path.shift();
      if( typeof root[dir] == 'undefined' ){
        root[dir] = path[0] == '' ? [] : {};
      }

      arguments.callee(root[dir], path, value);
    }else{
      if( root instanceof Array ){
        root.push(value);
      }else{
        root[path] = value;
      }
    }
  };
  var nvp = query.split('&');
  var data = {};
  for( var i = 0 ; i < nvp.length ; i++ ){
    var pair = nvp[i].split('=');
    var name = decodeURIComponent(pair[0]);
    var value = decodeURIComponent(pair[1]);

    var path = name.match(/(^[^\[]+)(\[.*\]$)?/);
    var first = path[1];
    if(path[2]){
      //case of 'array[level1]' || 'array[level1][level2]'
      path = path[2].match(/(?=\[(.*)\]$)/)[1].split('][')
    }else{
      //case of 'name'
      path = [];
    }
    path.unshift(first);

    setValue(data, path, value);
  }
  return data;
}

function register_group(groupname, groupselectselector, groupargappendselector) {
    var thisgroupappendselector = _.replace( groupargappendselector, '{groupname}', groupname );
    $( thisgroupappendselector ).click( function(e) {
        // don't process external links #71
        if (link_is_external(this)) return;
        e.preventDefault();
        var group = $( groupselectselector ).val();

        var basequery =  $(this).attr('href').split('?');
        var args = {}
        if (basequery.length > 1) {
            args = deparam(basequery[1]);
        }
        args[groupname] = group;
        location.href = basequery[0] + '?' + $.param(args);
    });
}
