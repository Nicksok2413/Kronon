# Makefile - Единая точка входа для управления проектом

# Переменные для удобства
COMPOSE_DEV = docker compose
COMPOSE_TEST = docker compose -f docker-compose.test.yml
COMPOSE_INFRA = docker compose --profile infra

# .PHONY гарантирует, что make не будет путать эти команды с именами файлов
.PHONY: help install run up down rebuild infra-up prune logs migrations migrate superuser clear-migrations reset-migrations lint lint-fix format types populate test-up test-down test test-clean check check-all clean

# Команда по умолчанию, которая будет вызвана при запуске `make`
default: help

# Цвета
RESET  := $(shell tput -Txterm sgr0)
RED    := $(shell tput -Txterm setaf 1)
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)

help:
	@echo "${GREEN}Kronon Management Commands:${RESET}"
	@echo ""
	@echo "Установка зависимостей и запуск локального сервера разработки:"
	@echo "  install         	- Установить Python зависимости"
	@echo "  run             	- Запустить локальный сервер разработки"
	@echo ""
	@echo "Управление Docker окружением:"
	@echo "  up             	- Запустить все сервисы в фоновом режиме"
	@echo "  down           	- Остановить все сервисы"
	@echo "  rebuild        	- Пересобрать образы и запустить сервисы"
	@echo "  infra-up        	- Запустить все сервисы вместе с PgBouncer (профиль infra) в фоновом режиме"
	@echo "  prune          	- Остановить сервисы и УДАЛИТЬ ВСЕ ДАННЫЕ (БД, логи)"
	@echo "  logs           	- Показать логи всех сервисов"
	@echo ""
	@echo "Управление миграциями базы данных:"
	@echo "  migrations     	- Создать новые миграции"
	@echo "  migrate        	- Применить миграции"
	@echo "  superuser      	- Создать суперпользователя (администратора)"
	@echo "  clear-migrations   - Удалить все файлы миграций (для удобства разработки)"
	@echo "  reset-migrations  	- Удалить все данные и пересоздать миграции (для удобства разработки)"
	@echo ""
	@echo "Проверка качества кода (Ruff + mypy):"
	@echo "  lint           	- Проверить код код с помощью Ruff"
	@echo "  lint-fix       	- Исправить код код с помощью Ruff"
	@echo "  format         	- Отформатировать код с помощью Ruff"
	@echo "  types          	- Проверить статическую типизацию mypy"
	@echo ""
	@echo "Тесты (Pytest):"
	@echo "  populate       	- Наполнить БД тестовыми данными (для удобства разработки)"
	@echo "  test-up     	  	- Запустить тестовое окружение в фоновом режиме"
	@echo "  test-down       	- Остановить тестовое окружение"
	@echo "  test           	- Запустить тесты pytest (тестовое окружение должно быть поднято)"
	@echo "  test-clean        	- Запустить тесты pytest с полной очисткой базы (тестовое окружение должно быть поднято)"
	@echo "  test-cov       	- Запустить тесты pytest с отчетом о покрытии кода (тестовое окружение должно быть поднято)"
	@echo ""
	@echo "Комплексные проверки:"
	@echo "  check          	- Запустить статический анализ (lint, types) последовательно"
	@echo "  check-all      	- Запустить все проверки (lint, types, test) последовательно"
	@echo "  clean          	- Очистить временные файлы (pycache, coverage, builds)"


# ------------------------------------------------------------------------------
# Установка зависимостей и локальный запуск
# ------------------------------------------------------------------------------
install:
	@echo "-> Установка зависимостей с помощью Poetry..."
	poetry install
	@echo "-> Зависимости успешно установлены."

run:
	@echo "-> Запуск локального ASGI сервера разработки (Uvicorn)..."
	poetry run uvicorn config.asgi:application --host 127.0.0.1 --port 8000 --reload
	@echo "-> Локальный сервер разработки остановлен."

# ------------------------------------------------------------------------------
# Управление Docker окружением
# ------------------------------------------------------------------------------
up:
	mkdir -p static media
	@echo "-> Запуск всех сервисов в фоновом режиме..."
	$(COMPOSE_DEV) up -d
	@echo "-> Сервисы успешно запущены."

down:
	@echo "-> Остановка всех сервисов..."
	$(COMPOSE_DEV) down
	@echo "-> Все сервисы остановлены."

rebuild: down
	@echo "-> Пересборка и запуск сервисов..."
	$(COMPOSE_DEV) up -d --build
	@echo "-> Сервисы успешно пересобраны и запущены."

infra-up:
	@echo "-> Запуск всех сервисов (вместе с PgBouncer) в фоновом режиме..."
	$(COMPOSE_INFRA) up -d
	@echo "-> Сервисы успешно запущены. Теперь можно подключиться к порту 6432."

prune:
	@if [ "$(CONFIRM)" != "y" ]; then \
		echo "${RED}ВНИМАНИЕ: Удаление всех данных в томах!${RESET}"; \
		read -p "Вы уверены? [y/N] " confirm; \
	else confirm="y"; fi; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		$(COMPOSE_DEV) down -v; \
		echo "-> Окружение очищено."; \
	else \
		echo "-> Отмена."; exit 1; \
	fi

logs:
	$(COMPOSE_DEV) logs -f

# ------------------------------------------------------------------------------
# Управление миграциями БД
# ------------------------------------------------------------------------------
migrations:
	poetry run python manage.py fix_migrations --hide
	@echo "-> Создание новых миграций..."
	poetry run python manage.py makemigrations
	@echo "-> Восстановление дерева зависимостей..."
	poetry run python manage.py fix_migrations --repair
	@echo "-> Миграции успешно созданы."

migrate:
	@echo "-> Применение миграций..."
	poetry run python manage.py migrate
	@echo "-> Миграции успешно применены."

superuser:
	@echo "-> Создание суперпользователя..."
	poetry run python manage.py createsuperuser
	@echo "-> Суперпользователь успешно создан."

clear-migrations:
	@if [ "$(CONFIRM)" != "y" ]; then \
		echo "${YELLOW}ВНИМАНИЕ: Удаление файлов миграций!${RESET}"; \
		read -p "Вы уверены? [y/N] " confirm; \
	else confirm="y"; fi; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		echo "-> Удаление файлов..."; \
		scripts/clear_migrations.sh; \
		echo "-> Очистка завершена."; \
	else \
		echo "-> Отмена."; exit 1; \
	fi

reset-migrations:
	@echo "${RED}ЗАПУСК ПОЛНОГО СБРОСА ПРОЕКТА...${RESET}"
	@$(MAKE) prune CONFIRM=y
	@$(MAKE) clear-migrations CONFIRM=y
	@$(MAKE) migrations
	@echo "${GREEN}Проект успешно сброшен и пересоздан.${RESET}"

# ------------------------------------------------------------------------------
# Проверка качества кода (Ruff + mypy)
# ------------------------------------------------------------------------------
lint:
	@echo '-> ${GREEN}Проверка кода с помощью Ruff linter...${RESET}'
	poetry run ruff check .

lint-fix:
	@echo "-> ${GREEN}Исправление кода с помощью Ruff linter...${RESET}"
	poetry run ruff check . --fix

format:
	@echo "-> ${GREEN}Форматирование кода с помощью Ruff formatter...${RESET}"
	poetry run ruff format .

types:
	@echo "-> ${GREEN}Проверка типов с помощью mypy...${RESET}"
	poetry run mypy .

# ------------------------------------------------------------------------------
# Тесты (Pytest)
# ------------------------------------------------------------------------------
populate:
	@echo "-> Наполнение БД тестовыми данными..."
	# Запускаем скрипт как модуль (-m), чтобы работал импорт config.settings
	poetry run python -m tests.seed

test-up:
	@echo "-> Запуск тестового окружения..."
	$(COMPOSE_TEST) up -d
	@echo "-> Тестовое окружение успешно запущено."

test-down:
	@echo "-> Остановка тестового окружения..."
	$(COMPOSE_TEST) down
	@echo "-> Тестовое окружение остановлено."

test:
	@echo "-> ${GREEN}Запуск тестов с (подключение к localhost:5433)...${RESET}"
	poetry run pytest

test-clean:
	$(COMPOSE_TEST) down -v
	$(MAKE) test

test-cov:
	@echo "-> ${GREEN}Запуск тестов с отчетом о покрытии (подключение к localhost:5433)...${RESET}"
	poetry run pytest --cov=apps/ --cov-report=term-missing --cov-report=html

check: lint types
	@echo "-> Статический анализ (lint, types) успешно пройден!"

check-all: lint types test
	@echo "-> Все проверки (включая тесты) успешно пройдены!"

clean:
	@echo "-> Очистка временных файлов (pycache, coverage, builds)..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf .coverage
	@echo "-> Очистка завершена."
