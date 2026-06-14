from django.db import models
import uuid
from django_mindoff import models as mindoff_models

# Create your models here.

class CustomerModel(mindoff_models.TimeStampModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column="id")
    name = models.CharField(max_length=120, db_column="name")
    email = models.EmailField(max_length=254, db_column="email")
    # Add model fields above this line -- (MANAGED BY MINDOFF. DO NOT TOUCH THIS LINE)

    class Meta:
        db_table = 'tbl_shop_customer'

    def __str__(self):
        return str(self.id)

class OrderModel(mindoff_models.TimeStampModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_column="id")
    customer_ref = models.ForeignKey(
            "shop.CustomerModel",
            on_delete=models.CASCADE,
            related_name='shop_order_customer_ref_rev',
            db_column='customer_ref_id'
        )

    product_name = models.CharField(max_length=160, db_column="product_name")
    quantity = models.PositiveIntegerField(db_column="quantity")
    status = models.CharField(max_length=32, default="created", db_column="status")
    # Add model fields above this line -- (MANAGED BY MINDOFF. DO NOT TOUCH THIS LINE)

    class Meta:
        db_table = 'tbl_shop_order'

    def __str__(self):
        return str(self.id)
