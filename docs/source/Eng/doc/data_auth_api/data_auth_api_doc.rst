=========
Test data
=========

* **Faker integration** — ``fake_email`` / ``fake_name`` / ``fake_value`` and
  friends; ``faker`` is a soft dependency.
* **Factories** — ``Factory(defaults)`` evaluates callable defaults per
  ``build()``; pre-built ``user_factory`` / ``order_factory`` /
  ``product_factory``.
* **Testcontainers** — ``start_postgres`` / ``start_redis`` /
  ``start_generic`` wrap testcontainers-python.
* **.env loader + ${ENV.X}** — ``load_env`` / ``expand_in_action`` so the
  same actions can target dev / staging / prod.
* **Data-driven runner** — ``load_dataset_csv`` / ``load_dataset_json`` /
  ``run_with_dataset`` with ``${ROW.col}`` placeholder expansion.

Test data & determinism
=======================

* ``snapshot.fixture_record.FixtureRecorder("fx.json", mode="auto")`` —
  record once, replay forever; modes ``record`` / ``replay`` / ``auto``.
* ``database.fixtures.load_fixture_file("seed.json")`` +
  ``load_into_connection(conn, fixture)`` — seed Postgres / MySQL /
  SQLite from ``{table: [rows]}`` JSON.

Auth, API, database
===================

* **OAuth2 / OIDC** — ``client_credentials_token`` / ``password_grant_token``
  / ``refresh_token_grant`` with in-process token cache that refreshes 30 s
  before expiry.
* **HTTP API** — ``http_get`` / ``http_post`` / ``http_put`` / ``http_patch``
  / ``http_delete`` plus ``http_assert_status`` and
  ``http_assert_json_contains``.
* **Database** — ``db_query`` / ``db_assert_count`` / ``db_assert_value`` /
  ``db_assert_exists`` / ``db_assert_empty``; SQLAlchemy soft dependency,
  bound parameters only.

API & contract testing
======================

* ``api_mock.MockRouter().add(method, url_pattern, body=, status=, times=)``
  — supports literal, glob, and ``re:`` regex URL patterns; attach to a
  Playwright page with ``attach_to_page(page)``.
* ``contract_testing.validate_response(body, schema)`` — JSON-Schema
  subset (type / properties / required / items / enum / oneOf /
  additionalProperties); ``validate_against_openapi`` resolves
  ``$ref`` and looks up ``paths[…].responses[…]``.
* ``graphql.GraphQLClient(endpoint).execute(query, variables=)`` +
  ``extract_field(payload, "users[0].name")``.
* ``mock_services`` — ``MockOAuthServer``, ``MockSmtpServer``,
  ``MockS3Storage`` for offline CI runs.
