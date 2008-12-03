=======
blatter
=======

Blatter is a tiny tool for creating and publishing static web sites
built from dynamic templates.

When developing your site, you can work locally on your own computer
and view your work through a local web server Blatter provides.  All
of your URLs will work, relative and absolute.  And if you choose to
use dynamic templates for including common elements like headers and
footers, (or for more advanced templating features), those templates
will be rendered on the fly as you make changes and refine your work.

When you're satisfied with your changes, you can 'blat' the project
out into a folder containing a purely static version of the site.

Static files like images and css are copied over, and all of the
dynamic templates are rendered into a final static form.  The finished
product can then be uploaded to the live web site and published
immediately.

Tutorial
--------

Get started with ``blatter init``::

  $ blatter init --hello-world
  Blatting...
  Created directories static, templates, site, out
  Created blatter.ini
  Created hello world content.
  Try it out with 'blatter serve' and 'blatter blat'.
  Done.

The ``--hello-world`` creates a sample project for you.  There's some
static content (an image) and some templates.

  $ ls *
  blatter.ini

  out:

  site:
  index.html

  static:
  images/

  templates:
  base.html

Anything in 'site' will be rendered as a template and is available as
a URL.  Anything in 'static' is available as a URL too: the two
directories are combined together.

The 'templates' directory will also be searched for templates but is
not included in URLs.  It's a handy place to keep template fragments
and utilities that you want to use in published pages.

You can start a local web server::

  $ blatter serve
  Blatter server starting for:
  	http://localhost:8008/

   * Running on http://localhost:8008/
   * Restarting with reloader...
  ^Z

And if you fetch the / URL, blatter renders the template
``site/index.html`` and serves up the ``static/images/dot.png``.
You'd do it in a web browser, but here we'll show it in text:

  $ curl http://localhost:8008/

  <html>
    <head>
      <title>hello world!</title>
    </head>
    <body>

  <p>
    <img src="images/dot.png">
    blatter success!
  </p>

    </body>
  </html>

Satisfied with that, blatter will publish the entire site, combining
everything in ``static`` with a rendered version of everything in ``site``.

  $ blatter blat
  Merged static into out
  Generated 1 files in out
  $ ls out
  images/		index.html
  $ cat out/index.html
  <html>
    <head>
      <title>hello world!</title>
    </head>
    <body>

  <p>
    <img src="images/dot.png">
    blatter success!
  </p>

    </body>
  </html>

You can even send that directly to a remote server if you like:

  $ blatter publish --destination=www.my.host:/var/www/mysite/htdocs/


Configuration
-------------

``blatter init`` will create a basic configuration for you in
``blatter.ini``.  Any of the directories can be changed to suit your
tastes.


Nested Sites and Chaining Blatters
----------------------------------

If your site will reside somewhere other than / on the remote server,
you can set the ``url_prefix`` configuration option to match the
prefix on the remote server, for example '~jek/'.

Blatter can also manage multiple sites within a single virtual
server.  Say you have the following structure::

  /*
  /products/blatter/*
  /products/squiznart/*

Each of these can be its own blatter project.  Each of the
`products/...` projects would set their ``url_prefix`` to match the
desired final URL.

If a ``/products/...`` project needs to use resources from the root
(`/`), such as `/images/logo.png`, the two projects can be linked
together during development so that URLs will resolve in the built-in
web server and you'll see all those shared images.

The only prerequisite for linking is that both blatter projects be
available on the filesystem.  To enable linking, configure the
``fallbacks`` for the project.  If a URL can't be found in the project
by normal means, each of the fallbacks will be tried in turn.  If the
fallbacks themselves have fallbacks, they're tried as well.

In the blatter.ini::

  url_prefix=/products/blatter

  fallbacks=root_website
  [fallback.root_website]
  location=../root_website

Author
------

Jason Kirtland <jek@discorporate.us>

Copyright Jason Kirtland, all rights reserved.
Available for use under the terms of the The MIT License, see LICENSE.
