"""Celery command line built on the app factory.

The ``celery -A`` CLI only accepts a module-level ``Celery`` instance,
which would be a global variable. This entry point builds the app with
``create_celery_app()`` and passes the arguments on to Celery, e.g.::

    python -m deribit_price_tracker.worker worker --beat --loglevel INFO
"""

import sys

from deribit_price_tracker.celery_app import create_celery_app
from deribit_price_tracker.config.base import Config


def main() -> None:
    create_celery_app(Config.from_env()).start(argv=sys.argv[1:])


if __name__ == "__main__":
    main()
