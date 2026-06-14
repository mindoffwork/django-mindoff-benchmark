from rest_framework import serializers
from . import models

class ProductModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ProductModel
        fields = '__all__'

class BenchmarkResultModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BenchmarkResultModel
        fields = '__all__'