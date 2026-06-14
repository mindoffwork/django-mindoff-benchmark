from rest_framework import serializers
from . import models

class CustomerModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CustomerModel
        fields = '__all__'

class OrderModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.OrderModel
        fields = '__all__'