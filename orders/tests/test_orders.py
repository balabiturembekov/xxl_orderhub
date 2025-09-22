import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from orders.models import Country, Factory, Order


class OrderTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Создаем пользователя
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Создаем тестовые данные
        self.country = Country.objects.create(name='Тестовая страна', code='TS')
        self.factory = Factory.objects.create(
            name='Тестовая фабрика',
            country=self.country,
            email='test@factory.com',
            contact_person='Тест Тестович'
        )
        
        # Создаем тестовый Excel файл (минимальный валидный XLSX)
        import zipfile
        import io
        
        # Создаем минимальный валидный XLSX файл
        xlsx_buffer = io.BytesIO()
        with zipfile.ZipFile(xlsx_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Минимальная структура XLSX
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
        
        self.excel_content = xlsx_buffer.getvalue()
        self.excel_file = SimpleUploadedFile(
            "test_order.xlsx",
            self.excel_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_create_order_view_get(self):
        """Тест GET запроса на страницу создания заказа"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('create_order'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Создать новый заказ')

    def test_create_order_view_post(self):
        """Тест POST запроса для создания заказа"""
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'title': 'Тестовый заказ',
            'description': 'Описание тестового заказа',
            'factory': self.factory.id,
            'comments': 'Тестовые комментарии'
        }
        
        files = {
            'excel_file': self.excel_file
        }
        
        response = self.client.post(reverse('create_order'), {**data, **files})
        self.assertEqual(response.status_code, 302)  # Редирект после успешного создания
        
        # Проверяем, что заказ создан
        order = Order.objects.get(title='Тестовый заказ')
        self.assertEqual(order.employee, self.user)
        self.assertEqual(order.factory, self.factory)
        self.assertEqual(order.status, 'uploaded')

    def test_order_list_view(self):
        """Тест страницы списка заказов"""
        # Создаем заказ
        order = Order.objects.create(
            title='Тестовый заказ',
            factory=self.factory,
            employee=self.user,
            excel_file=self.excel_file
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('order_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовый заказ')

    def test_order_detail_view(self):
        """Тест страницы детального просмотра заказа"""
        order = Order.objects.create(
            title='Тестовый заказ',
            factory=self.factory,
            employee=self.user,
            excel_file=self.excel_file
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('order_detail', kwargs={'pk': order.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Тестовый заказ')

    def test_send_order(self):
        """Тест отправки заказа на фабрику"""
        order = Order.objects.create(
            title='Тестовый заказ',
            factory=self.factory,
            employee=self.user,
            excel_file=self.excel_file
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('send_order', kwargs={'pk': order.pk}))
        self.assertEqual(response.status_code, 302)  # Редирект после отправки
        
        # Проверяем, что статус изменился
        order.refresh_from_db()
        self.assertEqual(order.status, 'sent')
        self.assertIsNotNone(order.sent_at)

    def test_upload_invoice_view_get(self):
        """Тест GET запроса на страницу загрузки инвойса"""
        order = Order.objects.create(
            title='Тестовый заказ',
            factory=self.factory,
            employee=self.user,
            excel_file=self.excel_file,
            status='sent'
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('upload_invoice', kwargs={'pk': order.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Загрузить инвойс')

    def test_upload_invoice_view_post(self):
        """Тест POST запроса для загрузки инвойса"""
        order = Order.objects.create(
            title='Тестовый заказ',
            factory=self.factory,
            employee=self.user,
            excel_file=self.excel_file,
            status='sent'
        )
        
        # Создаем тестовый PDF файл (минимальный валидный PDF)
        pdf_content = b'''%PDF-1.4
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
        
        pdf_file = SimpleUploadedFile(
            "test_invoice.pdf",
            pdf_content,
            content_type="application/pdf"
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        data = {
            'comments': 'Тестовые комментарии к инвойсу'
        }
        
        files = {
            'invoice_file': pdf_file
        }
        
        response = self.client.post(reverse('upload_invoice', kwargs={'pk': order.pk}), {**data, **files})
        self.assertEqual(response.status_code, 302)  # Редирект после загрузки
        
        # Проверяем, что статус изменился
        order.refresh_from_db()
        self.assertEqual(order.status, 'invoice_received')
        self.assertIsNotNone(order.invoice_file)

    def test_download_file(self):
        """Тест скачивания файлов"""
        order = Order.objects.create(
            title='Тестовый заказ',
            factory=self.factory,
            employee=self.user,
            excel_file=self.excel_file
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('download_file', kwargs={'pk': order.pk, 'file_type': 'excel'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/octet-stream')

    def test_get_factories_ajax(self):
        """Тест AJAX endpoint для получения фабрик"""
        response = self.client.get(reverse('get_factories'), {'country_id': self.country.id})
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Тестовая фабрика')

    def test_order_access_control(self):
        """Тест контроля доступа - пользователь видит только свои заказы"""
        # Создаем другого пользователя
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        
        # Создаем заказ для другого пользователя
        other_order = Order.objects.create(
            title='Чужой заказ',
            factory=self.factory,
            employee=other_user,
            excel_file=self.excel_file
        )
        
        # Создаем заказ для текущего пользователя
        my_order = Order.objects.create(
            title='Мой заказ',
            factory=self.factory,
            employee=self.user,
            excel_file=self.excel_file
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        # Проверяем, что в списке заказов только мой заказ
        response = self.client.get(reverse('order_list'))
        self.assertContains(response, 'Мой заказ')
        self.assertNotContains(response, 'Чужой заказ')
        
        # Проверяем, что нельзя получить доступ к чужому заказу
        response = self.client.get(reverse('order_detail', kwargs={'pk': other_order.pk}))
        self.assertEqual(response.status_code, 404)


@pytest.mark.django_db
class OrderPytestTestCase:
    """Тесты с использованием pytest"""
    
    def test_order_creation(self):
        """Тест создания заказа"""
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
        
        assert order.title == 'Pytest Order'
        assert order.factory == factory
        assert order.employee == user
        assert order.status == 'uploaded'

    def test_order_status_changes(self):
        """Тест изменения статусов заказа"""
        user = User.objects.create_user(
            username='statususer',
            email='status@example.com',
            password='statuspass123'
        )
        
        country = Country.objects.create(name='Status Country', code='SC')
        factory = Factory.objects.create(
            name='Status Factory',
            country=country,
            email='status@factory.com'
        )
        
        order = Order.objects.create(
            title='Status Order',
            factory=factory,
            employee=user
        )
        
        # Тестируем изменение статуса на "отправлен"
        order.mark_as_sent()
        assert order.status == 'sent'
        assert order.sent_at is not None
        
        # Тестируем изменение статуса на "завершен"
        order.mark_as_completed()
        assert order.status == 'completed'
        assert order.completed_at is not None

    def test_order_properties(self):
        """Тест свойств заказа"""
        user = User.objects.create_user(
            username='propsuser',
            email='props@example.com',
            password='propspass123'
        )
        
        country = Country.objects.create(name='Props Country', code='PR')
        factory = Factory.objects.create(
            name='Props Factory',
            country=country,
            email='props@factory.com'
        )
        
        order = Order.objects.create(
            title='Props Order',
            factory=factory,
            employee=user
        )
        
        # Тестируем свойства
        assert order.days_since_upload >= 0
        assert order.days_since_sent is None  # Заказ еще не отправлен
        assert not order.needs_reminder  # Заказ только что создан
