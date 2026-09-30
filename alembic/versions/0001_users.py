"""Create operational users table."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('users',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('username',sa.String(120),nullable=False),sa.Column('password_hash',sa.String(300),nullable=False),sa.Column('role',sa.String(20),nullable=False),sa.CheckConstraint("role IN ('admin','analyst','viewer')",name='ck_user_role'))
    op.create_index('ix_users_username','users',['username'],unique=True)

def downgrade():
    op.drop_table('users')
