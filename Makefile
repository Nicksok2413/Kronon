# Makefile - Единая точка входа для управления проектом

# .PHONY гарантирует, что make не будет путать эти команды с именами файлов
.PHONY: help install run up down rebuild prune logs migrations migrate superuser clear_migrations lint lint-fix format types test check check-all clean

# Команда по умолчанию, которая будет вызвана при запуске `make`
default: help

# Цвета
GREEN  := $(shell tput -Txterm setaf 2)
RESET  := $(shell tput -Txterm sgr0)

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
	@echo "  prune          	- Остановить сервисы и УДАЛИТЬ ВСЕ ДАННЫЕ (БД, логи)"
	@echo "  logs           	- Показать логи всех сервисов"
	@echo ""
	@echo "Управление миграциями базы данных:"
	@echo "  migrations     	- Создать новые миграции"
	@echo "  migrate        	- Применить миграции"
	@echo "  superuser      	- Создать суперпользователя (администратора)"
	@echo "  clear_migrations   - Удалить все файлы миграций (для удобства разработки)"
	@echo ""
	@echo "Проверка качества кода и тесты:"
	@echo "  lint           - Проверить код код с помощью Ruff"
	@echo "  lint-fix       - Исправить код код с помощью Ruff"
	@echo "  format         - Отформатировать код с помощью Ruff"
	@echo "  types          - Проверить статическую типизацию mypy"
	@echo "  test           - Запустить тесты pytest"
	@echo "  test-cov       - Запустить тесты pytest с отчетом о покрытии кода"
	@echo "  check          - Запустить статический анализ (lint, types) последовательно"
	@echo "  check-all      - Запустить все проверки (lint, types, test) последовательно"
	@echo "  clean          - Очистить временные файлы (pycache, coverage, builds)"


# ------------------------------------------------------------------------------
# Установка зависимостей и локальный запуск
# ------------------------------------------------------------------------------
install:
	@echo "-> Установка зависимостей с помощью Poetry..."
	poetry install
	@echo "-> Зависимости успешно установлены."

run:
	@echo "-> Запуск локального сервера разработки..."
	poetry run python manage.py runserver
	@echo "-> Локальный сервер разработки успешно запущен."

# ------------------------------------------------------------------------------
# Управление Docker окружением
# ------------------------------------------------------------------------------
up:
	@echo "-> Запуск всех сервисов в фоновом режиме..."
	docker compose up -d
	@echo "-> Сервисы успешно запущены."

down:
	@echo "-> Остановка всех сервисов..."
	docker compose down
	@echo "-> Все сервисы остановлены."

rebuild: down
	@echo "-> Пересборка и запуск сервисов..."
	docker compose up -d --build
	@echo "-> Сервисы успешно пересобраны и запущены."

prune:
	@echo "ВНИМАНИЕ: Эта команда остановит контейнеры и УДАЛИТ ВСЕ ДАННЫЕ В ТОМАХ (volumes)."
	@read -p "Вы уверены, что хотите продолжить? [y/N] " confirm && \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		echo "-> Начинаем полную очистку..."; \
		docker compose down -v; \
		echo "-> Окружение полностью очищено."; \
	else \
		echo "-> Очистка отменена."; \
	fi

logs:
	docker compose logs -f

# ------------------------------------------------------------------------------
# Управление миграциями БД
# ------------------------------------------------------------------------------
migrations:
	@echo "-> Создание новых миграций..."
	poetry run python manage.py makemigrations
	@echo "-> Миграции успешно созданы."

migrate:
	@echo "-> Применение миграций..."
	poetry run python manage.py migrate
	@echo "-> Миграции успешно применены."

superuser:
	@echo "-> Создание суперпользователя..."
	poetry run python manage.py createsuperuser
	@echo "-> Суперпользователь успешно создан."

clear_migrations:
	@echo "ВНИМАНИЕ: Эта команда УДАЛИТ ВСЕ ФАЙЛЫ МИГРАЦИЙ."
	@read -p "Вы уверены, что хотите продолжить? [y/N] " confirm && \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		echo "-> Начинаем удаление файлов миграций..."; \
		scripts/clear_migrations.sh; \
		echo "-> Очистка завершена."; \
	else \
		echo "-> Очистка отменена."; \
	fi

# ------------------------------------------------------------------------------
# Проверка качества кода и тесты
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

test:
	@echo "-> ${GREEN}Запуск тестов с (подключение к localhost:5432)...${RESET}"
	poetry run pytest

test-cov:
	@echo "-> ${GREEN}Запуск тестов с отчетом о покрытии (подключение к localhost:5432)...${RESET}"
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
