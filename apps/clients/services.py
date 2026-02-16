"""
Сервисы (Write Logic) для приложения Clients.
Отвечают за создание, обновление и удаление данных.
"""

from loguru import logger as log

from apps.clients.models import Client
from apps.clients.schemas.client import ClientCreate, ClientUpdate
from apps.clients.selectors import get_client_by_id


async def create_client(data: ClientCreate) -> Client:
    """
    Создает нового клиента в системе.

    Args:
        data (ClientCreate): Валидированные входные данные из API (Pydantic схема).

    Returns:
        Client: Созданный объект клиента с подгруженными связями.
    """
    log.info(f"Начало создания клиента (УНП: {data.unp}, название: {data.name})")

    # Формируем основной payload для полей модели (name, unp, accountant_id и т.д.)
    # Исключаем contact_info, чтобы обработать его отдельно
    # exclude_unset=True: берем только то, что пришло с фронта
    payload = data.model_dump(exclude_unset=True, exclude={"contact_info"})

    # Формируем данные для JSONField (contact_info)
    # mode="json": превращает UUID -> str, Enum -> str (то, что нужно для JSON)
    # exclude_none=True: удаляем пустые ключи, чтобы не хранить мусор в БД ({"email": null})
    contact_info_json = data.contact_info.model_dump(mode="json", exclude_none=True)

    # Добавляем обработанный JSON в payload
    payload["contact_info"] = contact_info_json

    # Создаем объект
    # Django ORM сам разберется: UUID-объекты пойдут в UUIDField, а словарь - в JSONField
    try:
        client = await Client.objects.acreate(**payload)
        log.info(f"Клиент успешно создан (ID: {client.id})")
    except Exception as exc:
        log.error(f"Ошибка при создании клиента (УНП: {data.unp}): {exc}")
        raise

    # Если API не нужно подгружать связи для ответа, просто возвращаем созданный объект
    # acreate возвращает "голый" объект (ID и базовые поля), но не делает join'ы
    # return client

    # Если API должен вернуть схему ClientOut с полными данными связей (department, accountant и т.д.)
    # Получаем актуальные данные через Селектор с подгрузкой связей (чтобы ответ соответствовал схеме ClientOut)
    created_client = await get_client_by_id(client_id=client.id)

    # Для Mypy: созданный объект существует, но get_client_by_id возвращает Client | None
    if not created_client:
        # Это исключительная ситуация, которая не должна произойти в транзакции
        log.critical(f"Клиент (ID: {client.id}) не найден после создания!")
        raise RuntimeError(f"Клиент (ID: {client.id}) не найден после создания")

    # Возвращаем данные созданного клиента
    return created_client


async def update_client(client: Client, data: ClientUpdate) -> Client:
    """
    Выполняет частичное обновление данных клиента (PATCH).

    Обрабатывает как стандартные поля модели, так и вложенное JSON-поле
    contact_info через специальный метод модели.

    Args:
        client (Client): Объект клиента (уже полученный из БД).
        data (ClientUpdate): Данные для обновления.

    Returns:
        Client: Обновленный объект с подгруженными связями.
    """
    # Логируем, что именно мы пытаемся обновить (ключи)
    changed_fields = data.model_dump(exclude_unset=True).keys()
    log.info(f"Обновление клиента (ID: {client.id}). Поля: {list(changed_fields)}")

    # Формируем основной payload для полей модели (name, unp, accountant_id и т.д.)
    # Исключаем contact_info, чтобы обработать его отдельно
    # exclude_unset=True: берем только то, что пришло с фронта
    payload = data.model_dump(exclude_unset=True, exclude={"contact_info"})

    # Обновляем стандартные поля (name, unp, accountant_id и т.д.)
    for field, value in payload.items():
        setattr(client, field, value)

    # Обновляем JSON поле (через метод в модели), если оно было передано
    contact_info_update = data.contact_info

    if contact_info_update is not None:
        # Передаем Pydantic-схему в метод модели
        # Метод модели сам вызовет model_dump(mode="json")
        client.patch_contact_data(contact_info_update)

    # Сохраняем (валидация полей модели вызовется здесь)
    try:
        await client.asave()
        log.debug(f"Клиент (ID: {client.id}) сохранен в БД")
    except Exception as exc:
        log.error(f"Ошибка при сохранении клиента (ID: {client.id}): {exc}")
        raise

    # Получаем актуальные данные через Селектор с подгрузкой связей (чтобы ответ соответствовал схеме ClientOut)
    updated_client = await get_client_by_id(client_id=client.id)

    # Для Mypy: обновляемый объект существует, но get_client_by_id возвращает Client | None
    if not updated_client:
        # Это исключительная ситуация, которая не должна произойти в транзакции
        log.critical(f"Клиент (ID: {client.id}) исчез после обновления!")
        raise RuntimeError(f"Клиент (ID: {client.id}) исчез после обновления")

    # Возвращаем актуальные данные
    return updated_client
