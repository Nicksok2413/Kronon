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
        data (ClientCreate): Валидированные входные данные из API.

    Returns:
        Client: Созданный объект с подгруженными связями.
    """
    # Логируем бизнес-контекст операции
    log.info(f"Start creating client. UNP: {data.unp}, Name: {data.name}")

    try:
        # Формируем основной payload для полей модели (name, unp, accountant_id и т.д.)
        # Исключаем contact_info, чтобы обработать его отдельно
        # exclude_unset=True: берем только то, что пришло с фронта
        payload = data.model_dump(exclude_unset=True, exclude={"contact_info"})

        # Формируем данные для JSONField (contact_info)
        # mode="json": превращает UUID/Enum в str
        # exclude_none=True: удаляем пустые ключи, чтобы не хранить мусор в БД ({"email": null})
        contact_info_json = data.contact_info.model_dump(mode="json", exclude_none=True)

        # Добавляем обработанный JSON в payload
        payload["contact_info"] = contact_info_json

        # Создаем объект
        # Django ORM сам разберется: UUID-объекты пойдут в UUIDField, а словарь - в JSONField
        client = await Client.objects.acreate(**payload)
        log.info(f"Client created successfully. ID: {client.id}")

        # .acreate возвращает "чистый" объект (ID и базовые поля), а схема ClientOut требует вложенных объектов
        # Делаем рефреш через селектор с подгрузкой связей (department, accountant и т.д.) для корректного ответа API
        full_client = await get_client_by_id(client.id)

        # Теоретически невозможно, что его нет, но для Mypy:
        if not full_client:
            log.critical(f"Client {client.id} disappeared after creation!")
            raise RuntimeError(f"Client {client.id} not found immediately after creation.")

        # Возвращаем созданный объект с полными данными
        return full_client

    except Exception as exc:
        # Логируем контекст ошибки перед тем, как она уйдет в глобальный хендлер
        log.error(f"Failed to create client (UNP: {data.unp}). Error: {exc}")
        raise


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
    # Логируем, какие поля меняются
    changed_fields = data.model_dump(exclude_unset=True).keys()
    log.info(f"Start updating client {client.id}. Fields: {list(changed_fields)}")

    try:
        # Формируем основной payload для полей модели (name, unp, accountant_id и т.д.)
        # Исключаем contact_info, чтобы обработать его отдельно
        # exclude_unset=True: берем только то, что пришло с фронта
        payload = data.model_dump(exclude_unset=True, exclude={"contact_info"})

        # JSON поле (если оно было передано)
        contact_info_update = data.contact_info

        # Обновляем стандартные поля (name, unp, accountant_id и т.д.)
        for field, value in payload.items():
            setattr(client, field, value)

        # Обновляем JSON поле через метод модели (умное слияние)
        if contact_info_update is not None:
            # Передаем Pydantic-схему в метод модели
            # Метод модели сам вызовет model_dump(mode="json")
            client.patch_contact_data(contact_info_update)

        # Сохраняем
        await client.asave()
        log.debug(f"Client {client.id} saved to DB.")

        # Делаем рефреш через селектор с подгрузкой связей (актуальные связи и updated_at) для корректного ответа API
        updated_client = await get_client_by_id(client_id=client.id)

        # Теоретически невозможно, что его нет, но для Mypy:
        if not updated_client:
            log.critical(f"Client {client.id} disappeared after update!")
            raise RuntimeError("Client not found after update")

        # Возвращаем актуальные данные
        return updated_client

    except Exception as exc:
        # Логируем контекст ошибки перед тем, как она уйдет в глобальный хендлер
        log.error(f"Failed to update client {client.id}. Error: {exc}")
        raise


async def delete_client(client: Client) -> None:
    """
    Выполняет мягкое удаление клиента.

    Args:
        client (Client): Объект клиента.
    """
    log.info(f"Start deleting client {client.id} (Soft Delete).")

    try:
        await client.adelete()
        log.info(f"Client {client.id} successfully marked as deleted.")

    except Exception as exc:
        # Логируем контекст ошибки перед тем, как она уйдет в глобальный хендлер
        log.error(f"Failed to delete client {client.id}. Error: {exc}")
        raise
