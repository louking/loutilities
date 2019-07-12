files in `tables-assets` are used in conjunction with the classes in `tables.py`.

To use the `tables-assets` files, add this snippet to project `__init__.py` after app created. `asset_env` 
is `Environment` from `flask-assets` 

```python
# add loutilities tables-assets for js/css/template loading
# see https://adambard.com/blog/fresh-flask-setup/
#    and https://webassets.readthedocs.io/en/latest/environment.html#webassets.env.Environment.load_path
# loutilities.__file__ is __init__.py file inside loutilities; os.path.split gets package directory
loutilitiespath = os.path.join(os.path.split(loutilities.__file__)[0], 'tables-assets', 'static')

@app.route('/loutilities/static/<path:filename>')
def loutilities_static(filename):
    return send_from_directory(loutilitiespath, filename)

with app.app_context():
    # js/css files
    asset_env.append_path(app.static_folder)
    asset_env.append_path(loutilitiespath, '/loutilities/static')

    # templates
    loader = ChoiceLoader([
        app.jinja_loader,
        PackageLoader('loutilities', 'tables-assets/templates')
    ])
    app.jinja_loader = loader
```