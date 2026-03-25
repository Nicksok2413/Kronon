"""
Common constants of users app.
"""

from uuid import UUID

# --- System User ---

# UUID системного пользователя
# Статический UUIDv7 (timestamp=1)
# Всегда будет первым в сортировке по ID
SYSTEM_USER_ID = UUID("00000000-0001-7000-8000-000000000000")

# Email системного пользователя
SYSTEM_USER_EMAIL = "system@kronon.local"
