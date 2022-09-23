Tomate Break Screen Plugin
==========================

Tomate plugin that shows a full screen window which prevents users from using the computer during a break.

Optionally runs a command at the end of a pause to lock the screen.

Development
-----------

Install the following native dependencies in you system:

- Python3 
- pip
- make 
- git 
- git-flow
- tomate/tomate-gtk

Install the Python development dependencies:

> pip install --user black bumpversion copier pytest pytest-cov pytest-flake8 pytest-mock pre-commit

Testing
-------

Format the files using [black](https://pypi.org/project/black/):

> make format

Run test in your local environment:

> make test

Run test inside the docker:

> make docker-test

Test manually the plugin:

> ln -s ~/.local/share/tomate/plugins path/to/plugin/project/data/plugins
> tomate-gtk -v

Then activate the plugin through the settings.

Release
-------

Update the *[Unrelease]* section in the CHANGELOG.md file then:

> make release-[patch|minor|major]