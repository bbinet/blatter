import mimetypes
import os
import sys
import subprocess
from ConfigParser import ConfigParser
from StringIO import StringIO
import jinja2
from werkzeug.exceptions import abort, HTTPException, NotFound
from werkzeug import (
    BaseResponse,
    SharedDataMiddleware,
    append_slash_redirect,
    create_environ,
    responder,
    )


config_names = os.environ.get('BLATTER_CONFIG', 'blatter.ini, local.ini')
config_files = [fn.strip() for fn in config_names.split(',')]
del config_names

base_config="""\
[blatter]

static_dir=static
template_dir=templates
dynamic_dir=site
output_dir=out

# 'publish' target can be configured or use --destination
#publish_location=some.host:/remote/path/
#publish_location=/local/path

# 'serve' options
index_document=index.html
url_prefix=/

# 'serve' can add other blatters into the URL space.  If a URL can't be
# found in this blatter, each of the fallbacks will be tried in turn.
# If the fallbacks themselves have fallbacks, they're tried as well.
#
# Fallbacks are useful for splitting a site into semi-independent
# pieces.  For example, one might have separate blatters for '/'
# (holding global images and css), a blatter for '/projects/', and
# individual blatters for each project under /projects/.
#
#fallbacks=other_blatter
#[fallback.other_blatter]
#location=../other_blatter

"""

sample_data = (
    ('static_dir', 'images/dot.png', '''
     iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAAAXNSR0IArs4c6QAAAQxJREFUS
     MfF\nlS2Og0AYhh8qVm16Aq4wJKh1da3AkHCBOg6F4wJNMIjW1VWRMFfgBE2zYk1rPsgXwnYp
     O5O+luF9\nZr5f8Kzg2UfThAEQASmQAF/AN2CBGqiA1sbd/WWAacItcAA+/7jkDchs3J1mAUw
     TfgAFsH8xGiWQ\n27j7+RUg5mcJxRJdgI2GrEYHin+YI/8Wky+QmB8dFc+uz0mgquU6I6FzdQ
     PWNu7ufYgih+aIV6Rz\nkHrosVQDEg+ARAOMB4CZKlPn6gHWg7fVgNoDoNaAygOg0oBWmgOHj
     dYOAJnnmUNA1u+IoYpkdpQO\nzEu9G8ZlmsvIXaqLeDAJkDm+WfiScrwL3rMyXS9973oARrhX
     oQrRyeQAAAAASUVORK5CYII=\n'''),
    ('template_dir', 'base.html', '''
     eyUgc2V0IHRpdGxlID0gdGl0bGUgfCBkZWZhdWx0KCdoZWxsbyB3b3JsZCcpICV9CjxodG1sP
     gog\nIDxoZWFkPgogICAgPHRpdGxlPnt7IHRpdGxlIH19PC90aXRsZT4KICA8L2hlYWQ+CiAg
     PGJvZHk+\nCiAgICAgIHslIGJsb2NrIGNvbnRlbnQgJX0KICAgICAgeyUgZW5kYmxvY2sgJX0
     KICA8L2JvZHk+\nCjwvaHRtbD4=\n'''),
    ('dynamic_dir', 'index.html', '''
     eyUgZXh0ZW5kcyAiL2Jhc2UuaHRtbCIgJX0KeyUgc2V0IHRpdGxlID0gImhlbGxvIHdvcmxkI
     SIgJX0KeyUgYmxvY2sgY29udGVudCAlfQo8cD4KICA8aW1nIHNyYz0iaW1hZ2VzL2RvdC5wbm
     ciPgogIGJsYXR0ZXIgc3VjY2VzcyEKPC9wPgp7JSBlbmRibG9jayAlfQo=\n'''))

_configurations = {}
def load_config(root=None, from_disk=True):
    if root is None:
        root = os.path.abspath(os.curdir)
    if root in _configurations:
        return _configurations[root]

    ini = ConfigParser()
    ini.readfp(StringIO(base_config))
    if from_disk:
        loaded = ini.read(os.path.join(root, file) for file in config_files)
        if not loaded:
            raise IOError('No configuration found in %s' % root)
    config = configuration(ini.items('blatter'), root=root)
    for key, value in list(config.items()):
        if key.endswith('dir'):
            config[key.replace('_dir', '_path')] = os.path.join(root, value)
    for section in ini.sections():
        config[section] = configuration(ini.items(section))
    config['url_prefix'] = config.url_prefix.rstrip('/') + '/'
    _configurations[root] = config
    return config

class configuration(dict):
    """A friendlier container for config."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

def write_file(path, content, create_path=True, overwrite=True):
    if not overwrite and os.path.exists(path):
        return False
    if create_path:
        folder = os.path.dirname(path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
    fh = open(path, 'wb')
    fh.write(content)
    fh.close()
    return True

def template_loader_for(config):
    path = [ jinja2.loaders.FileSystemLoader(config.template_path),
             jinja2.loaders.FileSystemLoader(config.dynamic_path) ]
    path.extend(jinja2.loaders.FileSystemLoader(fallback.template_path)
                for fallback in flattened_fallback_configs_for(config))

    loader = jinja2.loaders.ChoiceLoader(path)
    return jinja2.Environment(loader=loader)

def template_viewer_factory(config):
    """Construct an app that renders and returns templates."""
    loader = template_loader_for(config)

    @responder
    def template_viewer(environ, start_response):
        prefix, path_info = config.url_prefix, environ['PATH_INFO']
        if not os.path.dirname(path_info).startswith(prefix.rstrip('/')):
            raise NotFound()
        path_info = path_info[len(prefix):]

        if path_info.endswith('/'):
            path_info += config.index_document

        fspath = os.path.join(config.dynamic_path, path_info.lstrip('/'))

        if not os.path.exists(fspath):
            raise NotFound()
        elif os.path.isdir(fspath):
            return append_slash_redirect(environ)

        template = loader.get_template(path_info)

        mimetype, _ = mimetypes.guess_type(path_info)
        mimetype = mimetype or 'text/plain'

        render_environ = dict(environ, PATH_INFO=path_info)
        render_environ['SCRIPT_NAME'] += prefix

        response = BaseResponse(mimetype=mimetype or 'text/plain')
        response.data = template.render(config=config, environ=environ)
        response.headers['Pragma'] = 'no-cache'
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'
        response.headers['Expires'] = 'Sun, 13 Aug 1995 13:00:00 GMT'
        return response
    return template_viewer

def served_view_factory(config):
    """Construct an app that merges static and dynamic into one URL space."""
    template_viewer = template_viewer_factory(config)

    static_backed = SharedDataMiddleware(template_viewer, {
        config.url_prefix: config.static_path,
        })

    def combined_viewer(environ, start_response):
        # enable index.html in static
        if environ['PATH_INFO'].endswith('/'):
            environ['PATH_INFO'] += config.index_document
        return static_backed(environ, start_response)
    return combined_viewer

def fallback_configs_for(config):
    """Yield configurations for blatters listed in config.fallbacks."""
    for spec in config.get('fallbacks', '').split(','):
        name = spec.strip()
        if not name:
            continue
        bucket = 'fallback.%s' % name
        if bucket not in config:
            print "No [%s] configuration set, skipping." % bucket
            continue
        location = config[bucket].get('location', '').strip()
        if not location:
            print "No 'location' set in [%s], skipping." % bucket
            continue
        other_root = os.path.abspath(os.path.join(config.root, location))
        try:
            yield load_config(root=other_root)
        except IOError:
            print "Warning: could not load fallback %s from %s, skipping." % (
                name, other_root)
            continue
    raise StopIteration()

def flattened_fallback_configs_for(config):
    children = []
    for child in fallback_configs_for(config):
        children.append(child)
        children.extend(flattened_fallback_configs_for(child))
    return children

def add_fallbacks(app, app_factory, config):
    """Wrap app and retry 404s against fallback blatters, recursively."""
    fallbacks = tuple(add_fallbacks(app_factory(fb), app_factory, fb)
                      for fb in fallback_configs_for(config))
    if not fallbacks:
        return app
    def app_with_fallbacks(environ, start_response):
        try:
            return app(environ, start_response)
        except NotFound:
            for fallback in fallbacks:
                try:
                    return fallback(environ, start_response)
                except NotFound:
                    pass
        raise NotFound()
    return app_with_fallbacks

def top_level_factory(config, debugger=True):
    """Produce a top-level WSGI app suitable for direct use by a server."""
    app = served_view_factory(config)

    if 'fallbacks' in config:
        app = add_fallbacks(app, served_view_factory, config)

    if debugger:
        from werkzeug import DebuggedApplication
        final_app = DebuggedApplication(app, evalex=True)
    else:
        @responder
        def final_app(environ, start_response):
            try:
                return app(environ, start_response)
            except HTTPException, exc:
                return exc
    return final_app

def fetch_body(app, path):
    environ = create_environ(path=path)

    def start_response(status, headers):
        start_response.code = int(status.split()[0])
    start_response.code = None

    content = ''.join(list(app(environ, start_response)))
    if start_response.code == 200:
        return content
    elif start_response.code // 100 == 3:
        abort(404)
    else:
        abort(start_response.code)

def find_dynamic_uris(config):
    uris, root = [], config.dynamic_path
    def walker(_, path, files):
        local = path[len(root):].lstrip('/')
        uris.extend(os.path.join(config.url_prefix, local, f)
                    for f in files if os.path.isfile(os.path.join(path, f)))
    os.path.walk(root, walker, None)
    return uris

def run_script():
    from werkzeug import script
    sys.exit(script.run(globals()))

def action_init(hello_world=False):
    """Blat out a new blatter configuration.

    Creates a number of empty directories and a config file, ready for
    use. Pass --hello-world to include sample content as a starting
    place.

    """
    config = load_config(from_disk=False)

    print "Blatting..."
    created = []
    for key in ('static_dir', 'template_dir', 'dynamic_dir', 'output_dir'):
        subdir = config['blatter'][key]
        if not os.path.exists(subdir):
            os.mkdir(subdir)
            created.append(subdir)
    if created:
        print "Created directories %s" % ', '.join(created)
    ini_name = config_files[0]
    if write_file(ini_name, base_config, overwrite=False):
        print "Created %s" % ini_name
    if hello_world:
        for bucket_attr, filepath, data in sample_data:
            root = getattr(config, bucket_attr)
            target = os.path.join(root, filepath)
            if not write_file(target, data.decode('base64'), overwrite=False):
                print "Warning: %s already exists, skipping." % target
        print "Created hello world content."
        print "Try it out with 'blatter serve' and 'blatter blat'."
    print "Done."

def action_serve(port=('p', 8008), use_reloader=True, debugger=True):
    """Start a local web server for content viewing."""
    from werkzeug import serving

    config = load_config()
    app = top_level_factory(config, debugger=debugger)

    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        print "Blatter server starting for:\n\thttp://localhost:%s%s\n" % (
            port, config.url_prefix)
    serving.run_simple('localhost', port, app, use_reloader)

def action_generate(verbose=('v', False)):
    """Process all content in the site folder and place in the output folder."""
    config = load_config()
    app = template_viewer_factory(config)

    wrote = 0
    prefix = config.url_prefix.rstrip('/') + '/'

    if verbose:
        print "Generating dynamic content in %s" % config.dynamic_dir
    for uri in find_dynamic_uris(config):
        try:
            if verbose:
                print " * Generating URL %s" % uri
            content = fetch_body(app, uri)
        except Exception, exc:
            print "FAIL: could not generate %s" % uri
            print exc
            continue
        out = os.path.join(config.output_path, uri.lstrip('/'))
        write_file(out, content, overwrite=True)
        wrote += 1
        if verbose:
            print " * Wrote: %s%s" % (config.output_dir, uri)
    print "Generated %s files in %s" % (wrote, config.output_dir)

def action_merge_static(verbose=('v', False)):
    """Copy static files into the output folder using rsync."""
    config = load_config()
    source = "%s/" % config.static_path.rstrip('/')

    target = "%s/" % os.path.join(config.output_path,
                                  config.url_prefix.lstrip('/'))
    if not os.path.exists(target):
        os.makedirs(target)
    args = ['rsync', '-rv', source, target]
    rsync = subprocess.Popen(args, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    res = rsync.wait()
    if res or verbose:
        print ' '.join(args)
        out, err = rsync.communicate()
        if out:
            print out
        if err:
            print >> sys.stderr, err
    print "Merged %s into %s" % (config.static_dir, config.output_dir)
    return res

def action_blat(verbose=('v', False)):
    """Combine static and dynamically generated files into the output folder.

    Runs 'merge_static' followed by 'generate'.

    """
    action_merge_static(verbose=verbose)
    action_generate(verbose=verbose)

def action_publish(verbose=('v', False), destination=''):
    """Push blatted files to a remote folder using rsync."""
    config = load_config()
    source = config.output_path.rstrip('/') + '/'
    if not destination:
        destination = config['blatter'].get('publish_location', '').strip()
    if not destination:
        print ("Can not publish: Define 'publish_location' in configuration "
               "or use --destination")
        sys.exit(1)

    args = ['rsync', '-rv', source, destination]
    if verbose:
        print ' '.join(args)
    return subprocess.Popen(args).wait()

def action_template_shell(ipython=True):
    """Start an interactive debugging shell.

    Two extras are in the shell namespace: 'loader', a template
    loader, and 'config', a blatter config.

    """
    config = load_config()
    env = dict(config=config,
               loader=template_loader_for(config))

    from werkzeug import script
    shell = script.make_shell(init_func=lambda: env)
    return shell(ipython=ipython)

if __name__ == '__main__':
    run_script()
