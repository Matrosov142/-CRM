# Runbook резервного копирования и восстановления RC1

**Область:** только изолированные staging/DR учения с синтетическими данными. Не запускайте восстановление поверх production и не копируйте production backup в staging. Текущая реализация backup собирает файлы и SHA-256, но **не шифрует** их; переносить незашифрованную копию во внешнее хранилище запрещено. Шифрование, retention и RPO/RTO для целевой инфраструктуры пока не настроены и требуют решения владельцев.

## Ответственные и параметры учения

- Incident/DR lead: __________
- DBA/оператор: __________
- Свидетель бизнес-проверки: __________
- Staging project/host (без секретов): __________
- Одобренные RPO: __________; RTO: __________
- Retention policy и шифрование/object storage: __________
- Дата, commit/image SHA, backup UTC timestamp: __________

## 1. Подготовка

1. Убедитесь, что цель — отдельная staging/restore среда, где нет production данных и маршрута к production.
2. Согласуйте окно, ответственных и тестовый критерий восстановления. Создайте синтетическую компанию, операции и тестовый документ. Зафиксируйте контрольные количества и суммы, которые сверите после восстановления.
3. Подтвердите, что `.env.pilot` содержит только staging secrets и недоступен другим пользователям. Не печатайте его, не прикладывайте к отчету и не копируйте в Git.
4. Подготовьте отдельный шифруемый носитель/object storage и ключи согласно утверждённой политике. Ключ не хранить рядом с архивом. Если шифрование ещё не настроено, учение ограничить локальным защищённым staging-хостом; не выполнять off-site копирование.

## 2. Создание backup

Штатный скрипт использует `.env.pilot`, `docker compose`, `pg_dump -Fc` для PostgreSQL и `tar.gz` для `/var/lib/potok-crm/documents`; создаёт `SHA256SUMS` и закрывает права каталога для group/other:

```bash
bash ops/backup-pilot.sh
```

Запишите путь каталога, UTC время начала/окончания, размер файлов и SHA-256. Не трактуйте SHA-256 как шифрование или защиту от подмены со стороны администратора хранилища. До переноса за пределы хоста примените утверждённое шифрование и проверьте доступность ключа для DR-ответственных.

## 3. Проверка целостности архива

Укажите ранее созданный каталог backup, не раскрывая секретов:

```bash
BACKUP_PATH=/absolute/path/to/backups/YYYYMMDDTHHMMSSZ
(cd "$BACKUP_PATH" && sha256sum -c SHA256SUMS)
test -s "$BACKUP_PATH/database.dump"
test -s "$BACKUP_PATH/documents.tar.gz"
```

При любой ошибке checksum прекратите восстановление, пометьте копию как непригодную и уведомите DR lead. Не исправляйте checksum вручную.

## 4. Восстановление PostgreSQL в отдельную тестовую БД

Используйте новую пустую БД с уникальным именем, например `potok_restore_YYYYMMDD`. Не удаляйте и не очищайте существующие базы. Команды выполняются только в staging Compose-проекте:

```bash
RESTORE_DB=potok_restore_YYYYMMDD
docker compose --env-file .env.pilot -f compose.pilot.yml exec -T db \
  sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" createdb -U potok_admin -T template0 "$1"' sh "$RESTORE_DB"
cat "$BACKUP_PATH/database.dump" | docker compose --env-file .env.pilot -f compose.pilot.yml exec -T db \
  sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore --exit-on-error -U potok_admin -d "$1" --no-owner' sh "$RESTORE_DB"
```

Сверьте миграционный head и число таблиц. Ожидаемый head для текущего RC1 — `0033_company_registration_rls`; ожидаемое число таблиц — 44. Если значения не совпали, остановите учение и расследуйте причину:

```bash
docker compose --env-file .env.pilot -f compose.pilot.yml exec -T db \
  sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U potok_admin -d "$1" -Atc "SELECT version_num FROM alembic_version"' sh "$RESTORE_DB"
docker compose --env-file .env.pilot -f compose.pilot.yml exec -T db \
  sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U potok_admin -d "$1" -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema = '\''public'\'' AND table_type = '\''BASE TABLE'\''"' sh "$RESTORE_DB"
```

Для полного DR acceptance отдельно поднимите приложение в изолированном Compose-проекте, явно направив runtime credential на восстановленную БД, и проверьте readiness, вход и контрольные синтетические записи. Не переключайте рабочий staging/production API на восстановленную БД без решения release owner.

## 5. Восстановление документов в отдельный временный каталог

Архив содержит верхний каталог `documents/`. Распакуйте его в отдельный временный путь, не поверх активного document volume:

```bash
RESTORE_FILES_DIR=/absolute/path/to/restore-documents
mkdir -m 700 -p "$RESTORE_FILES_DIR"
tar -xzf "$BACKUP_PATH/documents.tar.gz" -C "$RESTORE_FILES_DIR"
test -d "$RESTORE_FILES_DIR/documents"
```

Сверьте наличие и доступность заранее созданного синтетического файла, его размер и SHA-256 по контрольной ведомости учения. После проверки безопасно удалите временную копию согласно принятому процессу удаления и зафиксируйте результат; не включайте содержимое документа в отчет.

## 6. Замер RPO/RTO и завершение

- **RPO:** зафиксируйте timestamp последней подтверждённой синтетической операции перед аварийной точкой и последней такой операции, доступной после restore; разница — измеренная потеря данных.
- **RTO:** измерьте от объявления условной аварии до успешного readiness и проверки согласованного сценария в восстановленном изолированном приложении.
- Сравните измерения с утверждёнными целями. Без числовых RPO/RTO целей результат нельзя считать принятым.
- Запишите владельцев, UTC timestamps, SHA-256, миграционный head, число таблиц, итог файловой сверки, measured RPO/RTO, проблемы и решение PASS/FAIL.
- Удалите временную staging БД и файлы только по утверждённой процедуре после сбора evidence. Не удаляйте исходный backup до подтверждения копии в защищённом хранилище и retention policy.

| Поле учения | Результат |
|---|---|
| Backup UTC / проверка SHA-256 | __________ |
| DB restore head / число таблиц | __________ |
| Синтетическая БД сверена бизнес-свидетелем | __________ |
| Document sentinel/size/hash | __________ |
| Измеренный RPO / утверждённая цель | __________ |
| Измеренный RTO / утверждённая цель | __________ |
| Шифрование, remote copy, retention evidence | __________ |
| Итог / замечания / подписи DBA и DR lead | __________ |
