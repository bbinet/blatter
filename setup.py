"""blatter"""

setup_info = dict(
    name="blatter",
    description="blats out static web sites",
    version="0.5",

    author='Jason Kirtland',
    author_email='jek@discorporate.us',
    license='MIT License',
    url='http://discorporate.us/jek/projects/blatter/',

    packages=['blatter'],

    scripts = ['scripts/blatter'],
    entry_points = {
        'console_scripts': [ 'blatter=blatter:run_script' ] },

    install_requires = [
        'Werkzeug',
        'Jinja2',
        ],

     classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: Site Management',
        'Topic :: Software Development :: Pre-processors',
        'Topic :: Text Processing :: Markup :: HTML',
        'Topic :: Utilities',
        ]
    )

try:
    from setuptools import setup
    del setup_info['scripts']
except ImportError:
    for unsupported in ('entry_points', 'install_requires'):
        del setup_info[unsupported]
    from distutils.core import setup

setup(**setup_info)
