from rest_framework import generics, permissions
from orders.models import Invoice
from orders.views.serializers import PublicInvoiceSerializer


class PublicInvoiceList(generics.ListAPIView):
    queryset = Invoice.objects.all()
    serializer_class = PublicInvoiceSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        return self.queryset.get(id=self.kwargs["id"])
