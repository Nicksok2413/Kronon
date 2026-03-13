# """
# Админка журнала аудита.
# """
#
# from django.contrib import admin
# from django.utils.translation import gettext_lazy as _
# from pghistory.admin import EventsAdmin
# from rangefilter.filters import DateTimeRangeFilter
#
# from apps.common.models import KrononMiddlewareEvents
#
#
# @admin.register(KrononMiddlewareEvents)
# class KrononEventsAdmin(EventsAdmin):
#     """
#     Админка для просмотра аудита изменений (History).
#     Работает с ProxyFields и ContextJSONField.
#     """
#
#     list_display = (
#         "pgh_created_at",
#         "pgh_obj",
#         "pgh_label",
#         "user_display",
#         "correlation_id_display",
#         "ip_display",
#         "method_display",
#     )
#
#     list_filter = (
#         "pgh_label",
#         # Фильтрация по дате (UI с календарём) на уровне БД
#         ("pgh_created_at", DateTimeRangeFilter),
#         # Фильтрация по сервису и HTTP методу (PostgreSQL JSONB lookup)
#         ("pgh_context__service", admin.AllValuesFieldListFilter),
#         ("pgh_context__method", admin.AllValuesFieldListFilter),
#
#     )
#
#     search_fields = (
#         "pgh_context__user_email",
#         "pgh_context__correlation_id",
#         "pgh_context__ip_address",
#     )
#
#     # # Делаем JOIN клиента, чтобы не было N+1 запросов при отрисовке списка
#     list_select_related = ("pgh_obj",)
#
#     # Явно запрещаем массовые действия
#     actions = None
#
#     # Немного ускорит админку на больших объёмах
#     list_per_page = 10
#
#     @admin.display(description="User/Email")
#     def user_display(self, obj):
#         return obj.pgh_context.get("user_email") or obj.pgh_context.user
#
#     @admin.display(description="Trace ID")
#     def correlation_id_display(self, obj):
#         return obj.pgh_context.get("correlation_id")
#
#     @admin.display(description=_("IP"))
#     def ip_display(self, obj):
#         return obj.pgh_context.get("ip_address")
#
#     @admin.display(description=_("Method"))
#     def method_display(self, obj):
#         return obj.pgh_context.get("method")
