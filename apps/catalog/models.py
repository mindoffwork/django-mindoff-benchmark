from django.db import models
import uuid
from django_mindoff import models as mindoff_models

# Create your models here.

class ProductModel(mindoff_models.TimeStampModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column="id")
    sku = models.CharField(max_length=64, db_column="sku")
    name = models.CharField(max_length=160, db_column="name")
    price = models.FloatField(db_column="price")
    stock = models.IntegerField(db_column="stock")
    category = models.CharField(max_length=80, db_column="category")
    is_active = models.BooleanField(default=True, db_column="is_active")
    # Add model fields above this line -- (MANAGED BY MINDOFF. DO NOT TOUCH THIS LINE)

    class Meta:
        db_table = 'tbl_catalog_product'

    def __str__(self):
        return str(self.id)

class BenchmarkResultModel(mindoff_models.TimeStampModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column="id")
    scenario = models.CharField(max_length=80, db_column="scenario")
    approach = models.CharField(max_length=32, db_column="approach")
    row_count = models.IntegerField(db_column="row_count")
    time_ms = models.FloatField(db_column="time_ms")
    memory_mb = models.FloatField(db_column="memory_mb")
    query_count = models.IntegerField(db_column="query_count")
    # Add model fields above this line -- (MANAGED BY MINDOFF. DO NOT TOUCH THIS LINE)

    class Meta:
        db_table = 'tbl_catalog_benchmarkresult'

    def __str__(self):
        return str(self.id)
