from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from .models import UserProfile, Order, Factory, NotificationSettings, Notification, Country, Invoice, InvoicePayment


class CustomUserCreationForm(UserCreationForm):
    """
    Кастомная форма регистрации с полем email.
    
    Расширяет стандартную форму UserCreationForm, добавляя:
    - Поле email (обязательное)
    - Валидацию уникальности email
    - Автоматическое сохранение email в профиль пользователя
    """
    email = forms.EmailField(
        required=True,
        label="Email",
        help_text="Обязательное поле. Будет использоваться для уведомлений."
    )
    
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Добавляем CSS классы для стилизации
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['email'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})
    
    def clean_email(self):
        """
        Проверяем уникальность email.
        
        Returns:
            str: Валидный email
            
        Raises:
            forms.ValidationError: Если email уже используется
        """
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email
    
    def save(self, commit=True):
        """
        Сохраняем пользователя с email.
        
        Args:
            commit (bool): Сохранять ли в базу данных
            
        Returns:
            User: Созданный пользователь
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            # Создаем профиль пользователя
            UserProfile.objects.create(user=user)
        return user


class UserProfileForm(forms.ModelForm):
    """
    Форма для редактирования профиля пользователя.
    
    Позволяет пользователю изменять:
    - Email
    - Имя и фамилию
    - Дополнительную информацию
    """
    
    class Meta:
        model = UserProfile
        fields = ['first_name', 'last_name', 'phone', 'department', 'position']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'first_name': 'Имя',
            'last_name': 'Фамилия',
            'phone': 'Телефон',
            'department': 'Отдел',
            'position': 'Должность',
        }


class UserEmailForm(forms.ModelForm):
    """
    Форма для изменения email пользователя.
    
    Отдельная форма для изменения email с дополнительной валидацией.
    """
    
    class Meta:
        model = User
        fields = ['email']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'})
        }
        labels = {
            'email': 'Email'
        }
    
    def clean_email(self):
        """
        Проверяем уникальность email.
        
        Returns:
            str: Валидный email
            
        Raises:
            forms.ValidationError: Если email уже используется
        """
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")
        return email


class OrderForm(forms.ModelForm):
    """
    Форма для создания и редактирования заказов.
    
    Позволяет пользователю создавать и редактировать заказы.
    """
    
    class Meta:
        model = Order
        fields = ['title', 'description', 'factory', 'excel_file', 'invoice_file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'factory': forms.Select(attrs={'class': 'form-control'}),
            'excel_file': forms.FileInput(attrs={'class': 'form-control'}),
            'invoice_file': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'title': 'Название заказа',
            'description': 'Описание',
            'factory': 'Фабрика',
            'excel_file': 'Excel файл',
            'invoice_file': 'Инвойс',
        }


class InvoiceUploadForm(forms.ModelForm):
    """
    Форма для загрузки инвойса.
    
    Позволяет пользователю загружать инвойс для заказа.
    """
    
    class Meta:
        model = Order
        fields = ['invoice_file']
        widgets = {
            'invoice_file': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'invoice_file': 'Инвойс',
        }


class NotificationSettingsForm(forms.ModelForm):
    """
    Форма для настроек уведомлений.
    
    Позволяет пользователю настраивать параметры уведомлений.
    """
    
    class Meta:
        model = NotificationSettings
        fields = ['email_notifications', 'reminder_frequency', 'notify_uploaded_reminder', 'notify_sent_reminder', 'notify_invoice_received']
        widgets = {
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reminder_frequency': forms.Select(attrs={'class': 'form-control'}),
            'notify_uploaded_reminder': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_sent_reminder': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_invoice_received': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'email_notifications': 'Email уведомления',
            'reminder_frequency': 'Частота напоминаний',
            'notify_uploaded_reminder': 'Напоминания о загруженных заказах',
            'notify_sent_reminder': 'Напоминания об отправленных заказах',
            'notify_invoice_received': 'Уведомления о получении инвойсов',
        }


class NotificationFilterForm(forms.Form):
    """
    Форма для фильтрации уведомлений.
    
    Позволяет пользователю фильтровать уведомления по различным критериям.
    """
    
    notification_type = forms.ChoiceField(
        choices=[
            ('', 'Все типы'),
            ('order_uploaded', 'Заказ загружен'),
            ('order_sent', 'Заказ отправлен'),
            ('invoice_received', 'Инвойс получен'),
            ('order_completed', 'Заказ завершен'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    is_read = forms.ChoiceField(
        choices=[
            ('', 'Все'),
            ('true', 'Прочитанные'),
            ('false', 'Непрочитанные'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )


class CountryForm(forms.ModelForm):
    """
    Форма для создания и редактирования стран.
    
    Позволяет администратору управлять странами.
    """
    
    class Meta:
        model = Country
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'Название страны',
            'code': 'Код страны',
        }


class FactoryForm(forms.ModelForm):
    """
    Форма для создания и редактирования фабрик.
    
    Позволяет администратору управлять фабриками.
    """
    
    class Meta:
        model = Factory
        fields = ['name', 'country', 'email', 'contact_person', 'phone', 'address', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.Select(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Название фабрики',
            'country': 'Страна',
            'email': 'Email',
            'contact_person': 'Контактное лицо',
            'phone': 'Телефон',
            'address': 'Адрес',
            'is_active': 'Активна',
        }


class InvoiceForm(forms.ModelForm):
    """
    Форма для создания и редактирования инвойса.
    
    Содержит поля для основной информации об инвойсе:
    - Номер инвойса
    - Общая сумма к оплате
    - Срок оплаты
    - Комментарии
    """
    
    class Meta:
        model = Invoice
        fields = ['invoice_number', 'balance', 'due_date', 'notes']
        widgets = {
            'invoice_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите номер инвойса от фабрики'
            }),
            'balance': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Дополнительная информация об инвойсе'
            }),
        }
        labels = {
            'invoice_number': 'Номер инвойса',
            'balance': 'Общая сумма к оплате',
            'due_date': 'Срок оплаты',
            'notes': 'Комментарии',
        }
        help_texts = {
            'invoice_number': 'Уникальный номер инвойса от фабрики',
            'balance': 'Полная сумма по инвойсу в валюте заказа',
            'due_date': 'Дата, до которой должен быть оплачен инвойс',
        }
    
    def clean_balance(self):
        """Валидация суммы инвойса"""
        balance = self.cleaned_data.get('balance')
        if balance is not None and balance <= 0:
            raise forms.ValidationError("Сумма инвойса должна быть больше нуля.")
        return balance


class InvoicePaymentForm(forms.ModelForm):
    """
    Форма для добавления платежа по инвойсу.
    
    Содержит поля для информации о платеже:
    - Сумма платежа
    - Дата платежа
    - Тип платежа
    - Скриншот чека оплаты
    - Комментарии
    """
    
    class Meta:
        model = InvoicePayment
        fields = ['amount', 'payment_date', 'payment_type', 'payment_receipt', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'payment_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'payment_receipt': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,.pdf'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Дополнительная информация о платеже'
            }),
        }
        labels = {
            'amount': 'Сумма платежа',
            'payment_date': 'Дата платежа',
            'payment_type': 'Тип платежа',
            'payment_receipt': 'Скриншот чека оплаты',
            'notes': 'Комментарии',
        }
        help_texts = {
            'amount': 'Сумма платежа в валюте заказа',
            'payment_date': 'Дата, когда был произведен платеж',
            'payment_type': 'Тип платежа (депозит, финальный платеж и т.д.)',
            'payment_receipt': 'Фото или скриншот подтверждения оплаты (JPG, PNG, PDF)',
        }
    
    def __init__(self, *args, **kwargs):
        self.invoice = kwargs.pop('invoice', None)
        super().__init__(*args, **kwargs)
        
        # Устанавливаем текущую дату по умолчанию
        if not self.instance.pk:
            self.fields['payment_date'].initial = timezone.now().date()
    
    def clean_amount(self):
        """Валидация суммы платежа"""
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Сумма платежа должна быть больше нуля.")
        
        # Проверка, что сумма не превышает остаток по инвойсу
        if self.invoice and amount:
            remaining = self.invoice.remaining_amount
            if amount > remaining:
                raise forms.ValidationError(
                    f"Сумма платежа ({amount}) не может превышать остаток к доплате ({remaining})."
                )
        
        return amount
    
    def clean_payment_receipt(self):
        """Валидация файла чека оплаты"""
        receipt = self.cleaned_data.get('payment_receipt')
        if receipt:
            # Проверка размера файла (максимум 10MB)
            if receipt.size > 10 * 1024 * 1024:
                raise forms.ValidationError("Размер файла не должен превышать 10MB.")
        return receipt


class InvoiceWithPaymentForm(forms.Form):
    """
    Комбинированная форма для создания инвойса с первым платежом.
    
    Используется на странице загрузки инвойса для одновременного
    создания инвойса и добавления первого платежа.
    """
    
    # Поля инвойса
    invoice_number = forms.CharField(
        max_length=100,
        label="Номер инвойса",
        help_text="Уникальный номер инвойса от фабрики",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите номер инвойса от фабрики'
        })
    )
    balance = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        label="Общая сумма к оплате",
        help_text="Полная сумма по инвойсу в валюте заказа",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'placeholder': '0.00'
        })
    )
    due_date = forms.DateField(
        required=False,
        label="Срок оплаты",
        help_text="Дата, до которой должен быть оплачен инвойс",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    invoice_notes = forms.CharField(
        required=False,
        label="Комментарии к инвойсу",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Дополнительная информация об инвойсе'
        })
    )
    
    # Поля платежа
    payment_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        label="Сумма платежа",
        help_text="Сумма первого платежа",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'placeholder': '0.00'
        })
    )
    payment_date = forms.DateField(
        label="Дата платежа",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    payment_type = forms.ChoiceField(
        choices=InvoicePayment.PAYMENT_TYPE_CHOICES,
        label="Тип платежа",
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    payment_receipt = forms.FileField(
        label="Скриншот чека оплаты",
        help_text="Фото или скриншот подтверждения оплаты (JPG, PNG, PDF)",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,.pdf'
        })
    )
    payment_notes = forms.CharField(
        required=False,
        label="Комментарии к платежу",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Дополнительная информация о платеже'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Устанавливаем текущую дату по умолчанию
        self.fields['payment_date'].initial = timezone.now().date()
    
    def clean_balance(self):
        """Валидация суммы инвойса"""
        balance = self.cleaned_data.get('balance')
        if balance is not None and balance <= 0:
            raise forms.ValidationError("Сумма инвойса должна быть больше нуля.")
        return balance
    
    def clean_payment_amount(self):
        """Валидация суммы платежа"""
        amount = self.cleaned_data.get('payment_amount')
        balance = self.cleaned_data.get('balance')
        
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Сумма платежа должна быть больше нуля.")
        
        if balance and amount and amount > balance:
            raise forms.ValidationError(
                f"Сумма платежа ({amount}) не может превышать общую сумму инвойса ({balance})."
            )
        
        return amount
    
    def clean_payment_receipt(self):
        """Валидация файла чека оплаты"""
        receipt = self.cleaned_data.get('payment_receipt')
        if receipt:
            # Проверка размера файла (максимум 10MB)
            if receipt.size > 10 * 1024 * 1024:
                raise forms.ValidationError("Размер файла не должен превышать 10MB.")
        return receipt