"""
Сервисы (Write Logic) для приложения Clients.
Отвечают за создание, обновление и удаление данных.
"""

from apps.clients.models import Client
from apps.clients.schemas.client import ClientCreate, ClientUpdate


async def create_client(data: ClientCreate) -> Client:
    """
    Создает нового клиента в системе.

    Args:
        data: Валидированные данные из API (Pydantic схема).

    Returns:
        Client: Созданный объект клиента с подгруженными связями.
    """
    # Извлекаем данные, конвертируя вложенные Pydantic-модели в JSON-совместимые типы
    # mode="json" превратит UUID, Enum и вложенные схемы в строки/словари
    payload = data.model_dump(exclude_unset=True, mode="json")

    # Создаем объект
    # acreate возвращает "голый" объект (ID и базовые поля), но не делает join'ы
    client = await Client.objects.acreate(**payload)

    # Если API не нужно подгружать связи для ответа, просто возвращаем созданный объект
    # return client

    # Если API должен вернуть схему ClientOut с полными данными связей (department, accountant и т.д.)
    return (
        await Client.objects.active()
        .select_related("department", "accountant", "primary_accountant", "payroll_accountant", "hr_specialist")
        .aget(id=client.id)
    )


async def update_client(client: Client, data: ClientUpdate) -> Client:
    """
    Обновляет данные клиента (PATCH).

    Args:
        client: Объект клиента (уже полученный из БД).
        data: Схема с обновляемыми полями.

    Returns:
        Client: Обновленный объект с подгруженными связями.
    """
    # Разделяем обычные поля и JSON поля
    # model_dump(exclude_unset=True) вернет словарь только с переданными полями
    payload = data.model_dump(exclude_unset=True)

    contact_info_update = payload.pop("contact_info", None)

    # Обновляем простые поля (через setattr)
    for field, value in payload.items():
        setattr(client, field, value)

    # Обновляем JSON поле (через метод в модели)
    if contact_info_update is not None:
        # contact_info в payload - это словарь (из-за model_dump)
        # Преобразовываем его обратно в схему, чтобы передать типизированный объект в метод модели
        from apps.clients.schemas.client import ClientContactInfoUpdate

        contact_schema = ClientContactInfoUpdate(**contact_info_update)
        client.patch_contact_data(contact_schema)

    # Сохраняем (валидация модели вызовется здесь)
    await client.asave()

    # Возвращаем с подгрузкой связей (чтобы ответ соответствовал схеме ClientOut)
    return (
        await Client.objects.active()
        .select_related("department", "accountant", "primary_accountant", "payroll_accountant", "hr_specialist")
        .aget(id=client.id)
    )
