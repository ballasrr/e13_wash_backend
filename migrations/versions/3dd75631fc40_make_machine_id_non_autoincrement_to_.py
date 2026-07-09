"""make machine id non-autoincrement to match crestwave id

Revision ID: 3dd75631fc40
Revises: 815203f8f73a
Create Date: 2026-07-09 11:33:02.512283

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3dd75631fc40'
down_revision: Union[str, Sequence[str], None] = '815203f8f73a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # очищаем таблицу от тестовых данных с автоинкрементными ID (1,2,3...)
    op.execute("DELETE FROM transactions")
    op.execute("DELETE FROM machines")
    # отвязываем колонку id от последовательности (sequence) — теперь ID задаётся вручную
    op.execute("ALTER TABLE machines ALTER COLUMN id DROP DEFAULT")
    op.execute("DROP SEQUENCE IF EXISTS machines_id_seq")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("CREATE SEQUENCE IF NOT EXISTS machines_id_seq")
    op.execute("ALTER TABLE machines ALTER COLUMN id SET DEFAULT nextval('machines_id_seq')")