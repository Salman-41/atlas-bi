"""Background jobs use JSON serialization and explicit task registration."""
import os
from celery import Celery
celery=Celery('atlas',broker=os.getenv('ATLAS_REDIS_URL','redis://localhost:6379/0'),backend=os.getenv('ATLAS_REDIS_URL','redis://localhost:6379/0'))
celery.conf.update(task_serializer='json',result_serializer='json',accept_content=['json'],worker_concurrency=1,task_time_limit=3600,task_soft_time_limit=3500)

@celery.task(name='atlas.train_models')
def train_models():
    from atlas.ml import train_all
    return train_all(os.getenv('ATLAS_DATA_DIR', 'data'))
