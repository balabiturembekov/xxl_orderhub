from django import forms
from django.core.validators import FileExtensionValidator
from .models import Order, Factory, Country, NotificationSettings
from .validators import validate_excel_file, validate_pdf_file, validate_safe_filename


class OrderForm(forms.ModelForm):
    """Форма для создания заказа"""
    
    class Meta:
        model = Order
        fields = ['title', 'description', 'factory', 'excel_file', 'comments']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название заказа'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание заказа (необязательно)'
            }),
            'factory': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_factory'
            }),
            'excel_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.xlsx,.xls'
            }),
            'comments': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Комментарии (необязательно)'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Показываем только активные фабрики
        self.fields['factory'].queryset = Factory.objects.filter(is_active=True).select_related('country')
        self.fields['factory'].empty_label = "Выберите фабрику"
        
        # Добавляем валидацию для Excel файла
        self.fields['excel_file'].validators = [
            validate_excel_file
        ]
        self.fields['excel_file'].help_text = "Загрузите Excel файл с заказом (.xlsx или .xls)"
    
    def clean_excel_file(self):
        """Дополнительная валидация Excel файла"""
        excel_file = self.cleaned_data.get('excel_file')
        if excel_file:
            validate_safe_filename(excel_file.name)
        return excel_file


class InvoiceUploadForm(forms.Form):
    """Форма для загрузки инвойса"""
    
    invoice_file = forms.FileField(
        label="PDF файл инвойса",
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf']),
            validate_pdf_file
        ],
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf'
        }),
        help_text="Загрузите PDF файл с инвойсом"
    )
    
    def clean_invoice_file(self):
        """Дополнительная валидация PDF файла"""
        invoice_file = self.cleaned_data.get('invoice_file')
        if invoice_file:
            validate_safe_filename(invoice_file.name)
        return invoice_file
    
    comments = forms.CharField(
        label="Комментарии к инвойсу",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Дополнительная информация об инвойсе (необязательно)'
        })
    )


class OrderFilterForm(forms.Form):
    """Форма для фильтрации заказов"""
    
    STATUS_CHOICES = [('', 'Все статусы')] + Order.STATUS_CHOICES
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по названию, описанию или фабрике'
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    factory = forms.ModelChoiceField(
        queryset=Factory.objects.filter(is_active=True).select_related('country'),
        required=False,
        empty_label="Все фабрики",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        required=False,
        empty_label="Все страны",
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_country',
            'onchange': 'loadFactories()'
        })
    )


class CountryForm(forms.ModelForm):
    """Форма для создания/редактирования страны"""
    
    class Meta:
        model = Country
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название страны'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите код страны (например, RU)',
                'maxlength': '3'
            })
        }
    
    def clean_code(self):
        """Валидация кода страны"""
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper()
        return code


class FactoryForm(forms.ModelForm):
    """Форма для создания/редактирования фабрики"""
    
    class Meta:
        model = Factory
        fields = ['name', 'country', 'email', 'contact_person', 'phone', 'address', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название фабрики'
            }),
            'country': forms.Select(attrs={
                'class': 'form-select'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите email для отправки заказов'
            }),
            'contact_person': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Контактное лицо (необязательно)'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Телефон (необязательно)'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Адрес (необязательно)'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['country'].empty_label = "Выберите страну"
        self.fields['country'].queryset = Country.objects.all().order_by('name')


class NotificationSettingsForm(forms.ModelForm):
    """Форма для настроек уведомлений"""
    
    class Meta:
        model = NotificationSettings
        fields = [
            'email_notifications',
            'notify_invoice_received',
            'notify_uploaded_reminder',
            'notify_sent_reminder',
            'reminder_frequency'
        ]
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notify_invoice_received': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notify_uploaded_reminder': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notify_sent_reminder': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'reminder_frequency': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 30
            })
        }
        labels = {
            'email_notifications': 'Включить email уведомления',
            'notify_invoice_received': 'Уведомлять о получении инвойсов',
            'notify_uploaded_reminder': 'Напоминания о неотправленных заказах',
            'notify_sent_reminder': 'Напоминания о заказах без инвойсов',
            'reminder_frequency': 'Частота напоминаний (дни)'
        }
        help_texts = {
            'reminder_frequency': 'Как часто отправлять напоминания (1-30 дней)',
            'notify_uploaded_reminder': 'Напоминания о заказах, которые не отправлены более 7 дней',
            'notify_sent_reminder': 'Напоминания о заказах, которые отправлены, но инвойс не получен более 7 дней'
        }


class NotificationFilterForm(forms.Form):
    """Форма для фильтрации уведомлений"""
    
    TYPE_CHOICES = [
        ('', 'Все типы'),
        ('order_uploaded', 'Загрузка заказа'),
        ('order_sent', 'Отправка заказа'),
        ('invoice_received', 'Получение инвойса'),
        ('order_completed', 'Завершение заказа'),
        ('uploaded_reminder', 'Напоминание о загрузке'),
        ('sent_reminder', 'Напоминание об отправке'),
    ]
    
    STATUS_CHOICES = [
        ('', 'Все статусы'),
        ('unread', 'Непрочитанные'),
        ('read', 'Прочитанные'),
    ]
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по тексту уведомления...'
        })
    )
    
    notification_type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
