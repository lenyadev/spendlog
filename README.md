# Spendlog

REST API для учёта личных финансов: операции, категории, месячный лимит, отчёты.
Учебный проект для портфолио.

**Стек:** Python, FastAPI, PostgreSQL, SQLAlchemy 2.0 (async), Alembic, uv, ruff, pytest.

## Статус

Этап 0 (каркас): работают `/health` и `/health/db`. Остальное по [PLAN.md](PLAN.md), описание проекта в [PROJECT.md](PROJECT.md).

## Запуск локально

Нужны: Python, [uv](https://docs.astral.sh/uv/), Docker (OrbStack).

```bash
git clone https://github.com/lenyadev/spendlog.git
cd spendlog
cp .env.example .env
uv sync
docker compose up -d db
uv run uvicorn spendlog.main:app --reload
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs

## Проверка

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
```

## Разработка

```bash
uv run ruff check .
uv run ruff format .
uv run pytest -v
```

CI (GitHub Actions) запускает ruff и pytest на каждый push и pull request в `main`.

## Конфигурация

Переменные в `.env` (шаблон в `.env.example`):

| Переменная | Описание |
| --- | --- |
| `APP_NAME` | Название приложения |
| `APP_ENV` | Окружение (`development`) |
| `APP_VERSION` | Версия |
| `DATABASE_URL` | Строка подключения к PostgreSQL |
