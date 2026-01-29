from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = "Пользователи и Структура"

    def ready(self) -> None:
        """
        Переопределяем метод ready для импорта и регистрации сигналов.
        Метод вызывается при готовности приложения.
        """
        import apps.users.signals  # noqa: F401
