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
    # Преобразуем Pydantic модель в словарь
    client_data = data.model_dump(exclude_unset=True)

    # Создаем объект
    client = await Client.objects.acreate(**client_data)

    # Если нужно подгрузить связи для ответа (так как acreate не делает join'ы)
    # можно сделать refresh или просто вернуть то, что есть (но поля связей будут пустые)
    # Для REST обычно достаточно вернуть ID и базовые поля
    return client
