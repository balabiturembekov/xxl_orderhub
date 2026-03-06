from orders.models import Invoice
from rest_framework import serializers


class PublicInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "balance",
            "total_paid",
            "remaining_amount",
            "status",
            "created_at",
            "updated_at",
            "due_date",
            "notes",
        ]
