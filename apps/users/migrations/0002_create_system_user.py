from django.db import migrations
from apps.users.constants import SYSTEM_USER_EMAIL,  SYSTEM_USER_ID


def create_system_user(apps, schema_editor):
    User = apps.get_model("users", "User")
    # Используем get_or_create, чтобы миграция была идемпотентной (безопасной при повторных запусках)
    User.objects.get_or_create(
        id=SYSTEM_USER_ID,
        defaults={
            "email": SYSTEM_USER_EMAIL,
            "first_name": "System",
            "last_name": "API",
            "role": "sys_admin",  # Полные права для обхода проверок
            "is_active": False,  # Чтобы под ним нельзя было залогиниться
            "is_staff": False,
            "is_superuser": False,
        },
    )


def remove_system_user(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(id=SYSTEM_USER_ID).delete()


class Migration(migrations.Migration):

    dependencies = [('users', '0001_initial'),]

    operations = [
        migrations.RunPython(create_system_user, remove_system_user),
    ]
