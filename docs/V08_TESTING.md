# v0.8 — PostgreSQL integration tests

Тесты требуют две отдельные строки подключения к одноразовой БД, имя которой содержит `test`:
- `TEST_ADMIN_DATABASE_URL`: тестовый суперпользователь только для fixtures и cleanup;
- `TEST_RUNTIME_DATABASE_URL`: минимальная runtime-роль приложения.

1. Создать отдельную БД, например `potok_crm_test`.
2. Применить миграции ролью-владельцем.
3. Создать runtime-роль по `ops/runtime_role_template.sql`.
4. Запустить `pytest -m postgres_rls tests/test_postgres_rls_integration.py`.

Тесты создают и удаляют строки в `companies`, `users`, `memberships`. Только disposable test-БД.
Если URL отсутствуют или имя БД не содержит `test`, тесты пропускаются. Пропуск не является успешным тестом.
