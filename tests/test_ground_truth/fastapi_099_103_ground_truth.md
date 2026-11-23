v0.103.0 (2023-08-26)
Added support for openapi_examples in all FastAPI parameters (Path, Query, Header, Cookie, Body, Form, File).

v0.102.0 (2023-08-25)
Added support for disabling the separation of input and output JSON Schemas in OpenAPI with Pydantic v2, using separate_input_output_schemas=False.

v0.101.1 (2023-08-14)
Added printable details to ResponseValidationError so that response validation errors show up in server error logs.

v0.101.0 (2023-08-04)
Enabled Pydantic's serialization mode for responses, adding support for Pydantic's computed_field, better OpenAPI for response models with proper required attributes, and better generated clients.

v0.100.1 (2023-07-27)
Replaced MultiHostUrl with AnyUrl for compatibility with older versions of Pydantic v1.

v0.100.0 (2023-07-07)
Added support for Pydantic v2 (core rewritten in Rust) while keeping support for Pydantic v1, with tests for both versions and 100% coverage.

Path, Query, Header, Cookie, Body, Form and File accept the new Pydantic Field parameters (such as default_factory, validation_alias, serialization_alias, discriminator, strict, json_schema_extra), and the regex parameter was deprecated in favour of pattern.

Settings management moved to the separate pydantic-settings package (BaseSettings is imported from pydantic_settings), and "fastapi[all]" now also installs pydantic-settings and pydantic-extra-types.

v0.99.1 (2023-07-02)
Fixed JSON Schema handling so that booleans are accepted as valid JSON Schemas, e.g. additionalProperties: false.
