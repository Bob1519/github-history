Version 3.1.0 (2024-11-13)
Dropped support for Python 3.8 and raised the minimum dependency versions to the latest feature releases (Werkzeug >= 3.1, ItsDangerous >= 2.2, Blinker >= 1.9).

Added a configuration option (PROVIDE_AUTOMATIC_OPTIONS) to control whether Flask automatically answers OPTIONS requests.

Flask.open_resource, open_instance_resource and Blueprint.open_resource take an encoding parameter for text mode, defaulting to utf-8.

Request.max_content_length can be customized per request instead of only through the MAX_CONTENT_LENGTH config, and new MAX_FORM_MEMORY_SIZE and MAX_FORM_PARTS configs were added, with documentation about resource limits on the security page.

Added support for the Partitioned cookie attribute (CHIPS) through the SESSION_COOKIE_PARTITIONED config.

Changed .env loading so that `-e path` takes precedence over the default .env and .flaskenv files, and load_dotenv loads the default files in addition to a path unless load_defaults=False is passed.

Added secret key rotation with the SECRET_KEY_FALLBACKS config, a list of old secret keys that can still be used for unsigning.

Fixed how host_matching=True and subdomain_matching=False interact with SERVER_NAME; setting SERVER_NAME no longer restricts requests to only that domain.

Request.trusted_hosts is now checked during routing and can be set through the TRUSTED_HOSTS config.
