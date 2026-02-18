"""
Сигналы приложения Users.
Автоматически создают профиль при создании пользователя.
"""

from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver
from loguru import logger as log

from apps.users.models import Profile, User


@receiver(post_save, sender=User)
def manage_user_profile(sender: type[User], instance: User, created: bool, **kwargs: Any) -> None:
    """
    Сигнал для управления Профилем при сохранении Пользователя.
    Если User обновляется, сохраняет и Profile.

    Args:
        sender (Type[User]): Класс модели (User).
        instance (User): Экземпляр пользователя.
        created (bool): Флаг создания.
        **kwargs (Any): Доп. аргументы (включая 'raw').
    """
    # Если загружаем фикстуры (системные данные), сигналы не нужны
    if kwargs.get("raw", False):
        return

    try:
        if created:
            Profile.objects.create(user=instance)
            log.info(f"Signal: profile created for user {instance.email}. ID={instance.pk}")
        else:
            # Если профиль уже есть, просто сохраняем его
            # Используем hasattr, чтобы не упасть, если профиль вдруг удалили вручную
            if hasattr(instance, "profile"):
                instance.profile.save()
                log.debug(f"Signal: profile updated for user {instance.email}")
            else:
                # Если пользователя обновили, а профиля почему-то нет — создадим его (восстановление)
                Profile.objects.create(user=instance)
                log.warning(f"Signal: restored missing profile for user {instance.email}")

    except Exception as exc:
        # Логируем ошибку, если по какой-то причине профиль не создался
        log.exception(f"Error in signal manage_user_profile for user {instance.email}: {exc}")
