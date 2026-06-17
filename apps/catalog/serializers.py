from rest_framework import serializers
from . import models

class ProductListSerializer(serializers.ListSerializer):
    def update(self, instances, validated_data):
        updated_products = []
        for product, attrs in zip(instances, validated_data):
            updated_products.append(self.child.update(product, attrs))
        return updated_products

class ProductModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ProductModel
        fields = '__all__'
        list_serializer_class = ProductListSerializer

class BenchmarkResultModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.BenchmarkResultModel
        fields = '__all__'
