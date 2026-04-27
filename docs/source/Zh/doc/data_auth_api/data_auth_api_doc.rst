========
測試資料
========

* Faker 整合（軟相依）
* Factory 樣板
* Testcontainers（軟相依）
* ``.env`` 載入器 + ``${ENV.X}``
* 資料驅動 runner + ``${ROW.x}``

測試資料 / 確定性
=================

* ``snapshot.fixture_record.FixtureRecorder`` — 第一次跑記錄、之後重放
* ``database.fixtures`` — YAML/JSON → SQLAlchemy 連線 seed

驗證
====

* OAuth2 / OIDC（含 token cache）
* HTTP API + 斷言
* 資料庫驗證（SQLAlchemy 軟相依，bound parameters only）

API 與合約
==========

* ``api_mock.MockRouter`` — Playwright route() 上層的宣告式 mock
* ``contract_testing`` — JSON Schema 子集 + OpenAPI ``$ref`` 解析
* ``graphql.GraphQLClient`` — GraphQL HTTP client + ``extract_field``
* ``mock_services`` — SMTP / OAuth / S3 in-process mock
