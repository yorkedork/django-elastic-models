python ?= python3.4
venv ?= .env


# setup a virtualenv
.env:
	virtualenv --no-site-packages -p $(python) $(venv)
	$(venv)/bin/pip install -e .[test]

# run tests
test: .env
	$(venv)/bin/python runtests.py

# remove junk
clean:
	rm -rf $(venv)
	find . -iname "*.pyc" -or -iname "__pycache__" -delete
