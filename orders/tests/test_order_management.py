import pytest
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
from orders.models import Country, Factory, Order, OrderConfirmation, Invoice, InvoicePayment
from orders.views.order_views import OrderListView, OrderDetailView, create_order
from orders.views.confirmation_views import send_order, upload_invoice_form, upload_invoice_execute
from orders.forms import OrderForm, InvoiceWithPaymentForm
from orders.templatetags.file_utils import filesize, filename


class OrderManagementTestCase(TestCase):
    """Расширенные тесты для модуля управления заказами"""
    
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        
        # Создаем пользователя
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Создаем тестовые данные
        self.country = Country.objects.create(name='Тестовая страна', code='TS')
        self.factory_obj = Factory.objects.create(
            name='Тестовая фабрика',
            country=self.country,
            email='test@factory.com',
            contact_person='Тест Тестович'
        )
        
        # Создаем тестовый Excel файл
        self.excel_content = self._create_test_excel()
        self.excel_file = SimpleUploadedFile(
            "test_order.xlsx",
            self.excel_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Создаем тестовый PDF файл
        self.pdf_content = self._create_test_pdf()
        self.pdf_file = SimpleUploadedFile(
            "test_invoice.pdf",
            self.pdf_content,
            content_type="application/pdf"
        )

    def _create_test_excel(self):
        """Создает минимальный валидный Excel файл"""
        import zipfile
        import io
        
        xlsx_buffer = io.BytesIO()
        with zipfile.ZipFile(xlsx_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
</Types>''')
            zip_file.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''')
            zip_file.writestr('xl/workbook.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <sheets>
        <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
    </sheets>
</workbook>''')
            zip_file.writestr('xl/_rels/workbook.xml.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>''')
            zip_file.writestr('xl/worksheets/sheet1.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <sheetData>
        <row r="1">
            <c r="A1" t="str">
                <v>Test</v>
            </c>
        </row>
    </sheetData>
</worksheet>''')
        
        return xlsx_buffer.getvalue()

    def _create_test_pdf(self):
        """Создает минимальный валидный PDF файл"""
        return b'''%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Test PDF) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000204 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
297
%%EOF'''

    def test_order_form_validation(self):
        """Тест валидации формы заказа"""
        form_data = {
            'title': 'Тестовый заказ',
            'description': 'Описание заказа',
            'factory': self.factory_obj.id,
            'comments': 'Комментарии'
        }
        
        form = OrderForm(data=form_data, files={'excel_file': self.excel_file})
        self.assertTrue(form.is_valid())
        
        # Тест с пустым заголовком
        form_data['title'] = ''
        form = OrderForm(data=form_data, files={'excel_file': self.excel_file})
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_order_list_view_pagination(self):
        """Тест пагинации в списке заказов"""
        # Создаем много заказов для тестирования пагинации
        orders = []
        for i in range(25):  # Создаем 25 заказов
            order = Order.objects.create(
                title=f'Заказ {i+1}',
                factory=self.factory_obj,
                employee=self.user,
                excel_file=self.excel_file
            )
            orders.append(order)
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('order_list'))
        self.assertEqual(response.status_code, 200)
        
        # Проверяем, что есть пагинация
        self.assertContains(response, 'page')

    def test_order_list_view_filtering(self):
        """Тест фильтрации заказов"""
        # Создаем заказы с разными статусами
        order1 = Order.objects.create(
            title='Заказ 1',
            factory=self.factory_obj,
            employee=self.user,
            excel_file=self.excel_file,
            status='uploaded'
        )
        
        order2 = Order.objects.create(
            title='Заказ 2',
            factory=self.factory_obj,
            employee=self.user,
            excel_file=self.excel_file,
            status='sent'
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        # Фильтр по статусу "отправлен"
        response = self.client.get(reverse('order_list'), {'status': 'sent'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Заказ 2')
        self.assertNotContains(response, 'Заказ 1')

    def test_order_list_view_search(self):
        """Тест поиска заказов"""
        # Создаем заказы с разными названиями
        order1 = Order.objects.create(
            title='Заказ с уникальным названием',
            factory=self.factory_obj,
            employee=self.user,
            excel_file=self.excel_file
        )
        
        order2 = Order.objects.create(
            title='Обычный заказ',
            factory=self.factory_obj,
            employee=self.user,
            excel_file=self.excel_file
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        # Поиск по уникальному названию
        response = self.client.get(reverse('order_list'), {'search': 'уникальным'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Заказ с уникальным названием')
        self.assertNotContains(response, 'Обычный заказ')

    def test_order_detail_view_context(self):
        """Тест контекста страницы детального просмотра заказа"""
        order = Order.objects.create(
            title='Тестовый заказ',
            factory=self.factory_obj,
            employee=self.user,
            excel_file=self.excel_file
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('order_detail', kwargs={'pk': order.pk}))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('order', response.context)
        self.assertEqual(response.context['order'], order)

    def test_send_order_confirmation_creation(self):
        """Тест создания подтверждения при отправке заказа"""
        order = Order.objects.create(
            title='Тестовый заказ',
            factory=self.factory_obj,
            employee=self.user,
            excel_file=self.excel_file
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('send_order', kwargs={'pk': order.pk}))
        
        # Проверяем, что создано подтверждение
        confirmation = OrderConfirmation.objects.filter(
            order=order,
            action='send_order'
        ).first()
        
        self.assertIsNotNone(confirmation)
        self.assertEqual(confirmation.status, 'pending')

    def test_upload_invoice_form_view(self):
        """Тест страницы формы загрузки инвойса"""
        order = Order.objects.create(
            title='Тестовый заказ',
            factory=self.factory_obj,
            employee=self.user,
            excel_file=self.excel_file,
            status='sent'
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('upload_invoice_form', kwargs={'pk': order.pk}))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'InvoiceWithPaymentForm')

    def test_upload_invoice_execute_with_payment(self):
        """Тест загрузки инвойса с платежом"""
        order = Order.objects.create(
            title='Тестовый заказ',
            factory=self.factory_obj,
            employee=self.user,
            excel_file=self.excel_file,
            status='sent'
        )
        
        # Создаем подтверждение
        confirmation = OrderConfirmation.objects.create(
            order=order,
            action='upload_invoice',
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        form_data = {
            'invoice_number': 'INV-001',
            'balance': '1000.00',
            'due_date': '2024-12-31',
            'invoice_notes': 'Тестовый инвойс',
            'payment_amount': '500.00',
            'payment_date': '2024-01-15',
            'payment_type': 'deposit',
            'payment_notes': 'Тестовый платеж'
        }
        
        files = {
            'invoice_file': self.pdf_file,
            'payment_receipt': self.pdf_file
        }
        
        response = self.client.post(
            reverse('upload_invoice_execute', kwargs={'pk': order.pk}),
            {**form_data, **files}
        )
        
        self.assertEqual(response.status_code, 302)  # Редирект после успешной загрузки
        
        # Проверяем, что создан инвойс
        invoice = Invoice.objects.filter(order=order).first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.invoice_number, 'INV-001')
        
        # Проверяем, что создан платеж
        payment = InvoicePayment.objects.filter(invoice=invoice).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, 500.00)
        
        # Проверяем, что подтверждение одобрено
        confirmation.refresh_from_db()
        self.assertEqual(confirmation.status, 'approved')

    def test_file_size_display(self):
        """Тест отображения размеров файлов"""
        # Тест функции filesize
        size = filesize(self.excel_file)
        self.assertIsInstance(size, str)
        self.assertIn('B', size)
        
        # Тест функции filename
        name = filename(self.excel_file)
        self.assertEqual(name, 'test_order.xlsx')

    def test_order_status_transitions(self):
        """Тест переходов статусов заказа"""
        order = Order.objects.create(
            title='Тестовый заказ',
            factory=self.factory_obj,
            employee=self.user,
            excel_file=self.excel_file
        )
        
        # uploaded -> sent
        order.mark_as_sent()
        self.assertEqual(order.status, 'sent')
        self.assertIsNotNone(order.sent_at)
        
        # sent -> invoice_received
        order.mark_invoice_received(self.pdf_file)
        self.assertEqual(order.status, 'invoice_received')
        self.assertIsNotNone(order.invoice_file)
        self.assertIsNotNone(order.invoice_received_at)
        
        # invoice_received -> completed
        order.mark_as_completed()
        self.assertEqual(order.status, 'completed')
        self.assertIsNotNone(order.completed_at)

    def test_order_reminder_logic(self):
        """Тест логики напоминаний"""
        # Создаем старый заказ (8 дней назад)
        old_date = timezone.now() - timedelta(days=8)
        order = Order.objects.create(
            title='Старый заказ',
            factory=self.factory_obj,
            employee=self.user,
            excel_file=self.excel_file,
            uploaded_at=old_date
        )
        
        # Проверяем, что нуждается в напоминании
        self.assertTrue(order.needs_reminder)
        self.assertEqual(order.days_since_upload, 8)
        
        # Отправляем заказ
        order.mark_as_sent()
        order.sent_at = timezone.now() - timedelta(days=8)
        order.save()
        
        # Проверяем напоминание для отправленного заказа
        self.assertTrue(order.needs_reminder)

    def test_order_access_permissions(self):
        """Тест прав доступа к заказам"""
        # Создаем другого пользователя
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        # Создаем заказ для другого пользователя
        other_order = Order.objects.create(
            title='Чужой заказ',
            factory=self.factory_obj,
            employee=other_user,
            excel_file=self.excel_file
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        # Пытаемся получить доступ к чужому заказу
        response = self.client.get(reverse('order_detail', kwargs={'pk': other_order.pk}))
        self.assertEqual(response.status_code, 404)
        
        # Пытаемся отправить чужой заказ
        response = self.client.post(reverse('send_order', kwargs={'pk': other_order.pk}))
        self.assertEqual(response.status_code, 404)

    def test_order_form_with_invalid_file(self):
        """Тест формы с невалидным файлом"""
        # Создаем невалидный файл (не Excel)
        invalid_file = SimpleUploadedFile(
            "test.txt",
            b"This is not an Excel file",
            content_type="text/plain"
        )
        
        form_data = {
            'title': 'Тестовый заказ',
            'description': 'Описание заказа',
            'factory': self.factory_obj.id,
            'comments': 'Комментарии'
        }
        
        form = OrderForm(data=form_data, files={'excel_file': invalid_file})
        self.assertFalse(form.is_valid())
        self.assertIn('excel_file', form.errors)

    def test_order_with_large_file(self):
        """Тест заказа с большим файлом"""
        # Создаем большой файл (но в пределах лимита)
        large_content = b'x' * (100 * 1024 * 1024)  # 100MB
        
        # Создаем минимальный Excel файл с большим размером
        import zipfile
        import io
        
        xlsx_buffer = io.BytesIO()
        with zipfile.ZipFile(xlsx_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
</Types>''')
            zip_file.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''')
            zip_file.writestr('xl/workbook.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <sheets>
        <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
    </sheets>
</workbook>''')
            zip_file.writestr('xl/_rels/workbook.xml.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>''')
            zip_file.writestr('xl/worksheets/sheet1.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <sheetData>
        <row r="1">
            <c r="A1" t="str">
                <v>Test</v>
            </c>
        </row>
    </sheetData>
</worksheet>''')
            # Добавляем большой контент
            zip_file.writestr('large_data.txt', large_content)
        
        large_excel_file = SimpleUploadedFile(
            "large_order.xlsx",
            xlsx_buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        form_data = {
            'title': 'Большой заказ',
            'description': 'Описание большого заказа',
            'factory': self.factory_obj.id,
            'comments': 'Комментарии'
        }
        
        form = OrderForm(data=form_data, files={'excel_file': large_excel_file})
        self.assertTrue(form.is_valid())


@pytest.mark.django_db
class OrderManagementPytestTestCase:
    """Тесты с использованием pytest для модуля управления заказами"""
    
    def test_order_model_properties(self):
        """Тест свойств модели Order"""
        user = User.objects.create_user(
            username='pytestuser',
            email='pytest@example.com',
            password='pytestpass123'
        )
        
        country = Country.objects.create(name='Pytest Country', code='PC')
        factory = Factory.objects.create(
            name='Pytest Factory',
            country=country,
            email='pytest@factory.com'
        )
        
        order = Order.objects.create(
            title='Pytest Order',
            factory=factory,
            employee=user
        )
        
        # Тестируем свойства
        assert order.days_since_upload >= 0
        assert order.days_since_sent is None
        assert not order.needs_reminder
        
        # Тестируем строковое представление
        assert str(order) == f"Pytest Order - Pytest Factory"

    def test_order_confirmation_workflow(self):
        """Тест рабочего процесса подтверждений"""
        user = User.objects.create_user(
            username='confuser',
            email='conf@example.com',
            password='confpass123'
        )
        
        country = Country.objects.create(name='Conf Country', code='CC')
        factory = Factory.objects.create(
            name='Conf Factory',
            country=country,
            email='conf@factory.com'
        )
        
        order = Order.objects.create(
            title='Conf Order',
            factory=factory,
            employee=user
        )
        
        # Создаем подтверждение
        confirmation = OrderConfirmation.objects.create(
            order=order,
            action='send_order',
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        assert confirmation.status == 'pending'
        assert confirmation.action == 'send_order'
        assert confirmation.order == order
        
        # Одобряем подтверждение
        confirmation.status = 'approved'
        confirmation.save()
        
        assert confirmation.status == 'approved'

    def test_invoice_creation_with_payment(self):
        """Тест создания инвойса с платежом"""
        user = User.objects.create_user(
            username='invoiceuser',
            email='invoice@example.com',
            password='invoicepass123'
        )
        
        country = Country.objects.create(name='Invoice Country', code='IC')
        factory = Factory.objects.create(
            name='Invoice Factory',
            country=country,
            email='invoice@factory.com'
        )
        
        order = Order.objects.create(
            title='Invoice Order',
            factory=factory,
            employee=user
        )
        
        # Создаем инвойс
        invoice = Invoice.objects.create(
            order=order,
            invoice_number='INV-001',
            balance=1000.00,
            due_date=timezone.now().date() + timedelta(days=30)
        )
        
        assert invoice.order == order
        assert invoice.balance == 1000.00
        assert invoice.status == 'pending'
        
        # Создаем платеж
        payment = InvoicePayment.objects.create(
            invoice=invoice,
            amount=500.00,
            payment_date=timezone.now().date(),
            payment_type='deposit',
            created_by=user
        )
        
        assert payment.invoice == invoice
        assert payment.amount == 500.00
        assert payment.payment_type == 'deposit'
        
        # Проверяем, что статус инвойса изменился
        invoice.refresh_from_db()
        assert invoice.status == 'partial'
        assert invoice.total_paid == 500.00
        assert invoice.remaining_amount == 500.00
