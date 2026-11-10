from __future__ import annotations

import os
import sys
from getpass import getpass
from urllib.parse import quote_plus

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.models import AuditEvent, Company, Membership, User
from app.security import hash_password

_EMAIL_ADAPTER = TypeAdapter(EmailStr)


def normalize_email(value: str) -> str | None:
    try:
        return str(_EMAIL_ADAPTER.validate_python(value.strip())).lower()
    except ValidationError:
        return None


def main() -> int:
    # One-time bootstrap must bypass tenant RLS to create the first company,
    # user, membership and audit row. It uses the isolated admin credential,
    # never the schema owner or runtime connection.
    admin_password = os.environ.get("DB_ADMIN_PASSWORD")
    if not admin_password:
        print("Ошибка: DB_ADMIN_PASSWORD отсутствует; bootstrap не выполнен.")
        return 2
    database_url = (
        "postgresql+psycopg://potok_admin:"
        f"{quote_plus(admin_password)}@db:5432/potok_crm"
    )

    email = normalize_email(input("Email первого директора: "))
    if email is None:
        print("Некорректный email.")
        return 2

    company_name = input("Название компании: ").strip()
    if not company_name or len(company_name) > 200:
        print("Название компании обязательно (до 200 символов).")
        return 2

    password = getpass("Пароль (не менее 14 символов): ")
    confirmation = getpass("Повторите пароль: ")
    if len(password) < 14 or password != confirmation:
        print("Пароли не совпадают или короче 14 символов.")
        return 2

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine) as db:
            if db.scalar(select(func.count()).select_from(User)):
                print("Первый администратор уже создан. Команда заблокирована.")
                return 3
            company = Company(name=company_name, status="active")
            user = User(email=email, password_hash=hash_password(password), is_active=True)
            db.add_all([company, user])
            db.flush()
            membership = Membership(
                company_id=company.id,
                user_id=user.id,
                role="director",
                status="active",
            )
            db.add(membership)
            db.add(AuditEvent(
                company_id=company.id,
                actor_user_id=user.id,
                action="bootstrap.first_director_created",
                entity_type="membership",
                entity_id=str(membership.id),
                outcome="success",
                details={"role": "director"},
            ))
            db.commit()
            print(f"Создан первый директор компании «{company.name}».")
            print("Войдите через веб-интерфейс. Пароль не выводится.")
            return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
