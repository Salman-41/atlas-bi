import os
from alembic import context
from sqlalchemy import engine_from_config,pool
from atlas.models import Base
from pathlib import Path
from sqlalchemy.engine import make_url
config=context.config
config.set_main_option('sqlalchemy.url',os.getenv('ATLAS_DATABASE_URL','sqlite:///data/app.db').replace('%','%%'))
database_url = make_url(config.get_main_option('sqlalchemy.url'))
if database_url.drivername.startswith('sqlite') and database_url.database and database_url.database != ':memory:':
    Path(database_url.database).parent.mkdir(parents=True, exist_ok=True)
if context.is_offline_mode():
    context.configure(url=config.get_main_option('sqlalchemy.url'),target_metadata=Base.metadata,literal_binds=True)
    with context.begin_transaction(): context.run_migrations()
else:
    engine=engine_from_config(config.get_section(config.config_ini_section),prefix='sqlalchemy.',poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata)
        with context.begin_transaction(): context.run_migrations()
