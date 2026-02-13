"""
Сервисы (Write Logic) для приложения Clients.
Отвечают за создание, обновление и удаление данных.
"""

from apps.clients.models import Client
from apps.clients.schemas.client import ClientCreate


async def create_client(data: ClientCreate) -> Client:
    """
    Создает нового клиента в системе.

    Args:
        data: Валидированные данные из API (Pydantic схема).

    Returns:
        Client: Созданный объект клиента.
    """
    # Извлекаем данные, конвертируя вложенные Pydantic-модели в JSON-совместимые типы
    # mode="json" превратит UUID, Enum и вложенные схемы в строки/словари
    payload = data.model_dump(exclude_unset=True, mode="json")

    # Создаем объект
    client = await Client.objects.acreate(**payload)

    # Если API должен вернуть ClientOut с полными данными связей
    # (department, accountant и т.д.), нам нужно их подтянуть, так как acreate
    # возвращает "голый" объект
    return (
        await Client.objects.active()
        .select_related("department", "accountant", "primary_accountant", "payroll_accountant", "hr_specialist")
        .aget(id=client.id)
    )

    # Если не нужно подгружать связи для ответа (так как acreate не делает join'ы)
    # Для REST обычно достаточно вернуть ID и базовые поля
    # return client
