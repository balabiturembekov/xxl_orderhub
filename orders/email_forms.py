"""
Forms for email template management.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.template import Template, Context
from .models import EmailTemplate


class EmailTemplateForm(forms.ModelForm):
    """Form for creating and editing email templates"""
    
    class Meta:
        model = EmailTemplate
        fields = [
            'name', 'template_type', 'language', 'subject', 
            'html_content', 'text_content', 'is_active', 'is_default',
            'description', 'variables_help'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Введите название шаблона'
            }),
            'template_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'language': forms.Select(attrs={
                'class': 'form-control'
            }),
            'subject': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Тема письма с переменными'
            }),
            'html_content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 15,
                'placeholder': 'HTML содержимое письма'
            }),
            'text_content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': 'Текстовая версия письма'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Описание назначения шаблона'
            }),
            'variables_help': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Справка по доступным переменным'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Добавляем CSS классы для полей
        for field_name, field in self.fields.items():
            if field_name not in ['is_active', 'is_default']:
                field.widget.attrs.update({'class': 'form-control'})
    
    def clean_subject(self):
        """Валидация темы письма"""
        subject = self.cleaned_data.get('subject')
        if not subject:
            raise ValidationError('Тема письма обязательна')
        
        # Проверяем синтаксис шаблона
        try:
            Template(subject)
        except Exception as e:
            raise ValidationError(f'Ошибка в синтаксисе темы: {str(e)}')
        
        return subject
    
    def clean_html_content(self):
        """Валидация HTML содержимого"""
        html_content = self.cleaned_data.get('html_content')
        if not html_content:
            raise ValidationError('HTML содержимое обязательно')
        
        # Проверяем синтаксис шаблона
        try:
            Template(html_content)
        except Exception as e:
            raise ValidationError(f'Ошибка в синтаксисе HTML: {str(e)}')
        
        return html_content
    
    def clean_text_content(self):
        """Валидация текстового содержимого"""
        text_content = self.cleaned_data.get('text_content')
        if not text_content:
            raise ValidationError('Текстовое содержимое обязательно')
        
        # Проверяем синтаксис шаблона
        try:
            Template(text_content)
        except Exception as e:
            raise ValidationError(f'Ошибка в синтаксисе текста: {str(e)}')
        
        return text_content
    
    def clean(self):
        """Общая валидация формы"""
        cleaned_data = super().clean()
        
        # Проверяем уникальность шаблона по умолчанию
        if cleaned_data.get('is_default'):
            template_type = cleaned_data.get('template_type')
            language = cleaned_data.get('language')
            
            if template_type and language:
                existing_default = EmailTemplate.objects.filter(
                    template_type=template_type,
                    language=language,
                    is_default=True
                ).exclude(pk=self.instance.pk if self.instance else None)
                
                if existing_default.exists():
                    raise ValidationError(
                        f'Уже существует шаблон по умолчанию для типа "{template_type}" '
                        f'и языка "{language}". Сначала снимите флаг "По умолчанию" с существующего шаблона.'
                    )
        
        return cleaned_data
    
    def save(self, commit=True):
        """Сохранение с установкой создателя"""
        instance = super().save(commit=False)
        
        if self.user and not instance.pk:
            instance.created_by = self.user
        
        if commit:
            instance.save()
        
        return instance


class EmailTemplatePreviewForm(forms.Form):
    """Form for previewing email templates with test data"""
    
    template_id = forms.IntegerField(widget=forms.HiddenInput())
    
    # Тестовые данные
    order_title = forms.CharField(
        max_length=200,
        label='Название заказа',
        initial='Тестовый заказ',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    order_description = forms.CharField(
        label='Описание заказа',
        initial='Описание тестового заказа',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    factory_name = forms.CharField(
        max_length=200,
        label='Название фабрики',
        initial='Тестовая фабрика',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    factory_contact_person = forms.CharField(
        max_length=100,
        label='Контактное лицо',
        initial='Иван Иванов',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    employee_name = forms.CharField(
        max_length=100,
        label='Имя сотрудника',
        initial='Петр Петров',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    country_name = forms.CharField(
        max_length=100,
        label='Страна',
        initial='Германия',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    def get_test_context(self):
        """Получить тестовый контекст для рендеринга"""
        from django.utils import timezone
        
        return {
            'order': type('Order', (), {
                'title': self.cleaned_data.get('order_title', 'Тестовый заказ'),
                'description': self.cleaned_data.get('order_description', 'Описание тестового заказа'),
                'uploaded_at': timezone.now(),
                'status': 'uploaded',
                'comments': 'Тестовые комментарии',
            })(),
            'factory': type('Factory', (), {
                'name': self.cleaned_data.get('factory_name', 'Тестовая фабрика'),
                'email': 'test@factory.com',
                'contact_person': self.cleaned_data.get('factory_contact_person', 'Иван Иванов'),
                'phone': '+49 123 456 789',
                'address': 'Teststraße 123, 12345 Teststadt',
            })(),
            'employee': type('Employee', (), {
                'get_full_name': self.cleaned_data.get('employee_name', 'Петр Петров'),
                'username': 'testuser',
                'email': 'test@company.com',
            })(),
            'country': type('Country', (), {
                'name': self.cleaned_data.get('country_name', 'Германия'),
                'code': 'DE',
            })(),
        }


class EmailTemplateSearchForm(forms.Form):
    """Form for searching email templates"""
    
    SEARCH_CHOICES = [
        ('', 'Все типы'),
        ('factory_order', 'Заказ на фабрику'),
        ('order_confirmation', 'Подтверждение заказа'),
        ('order_notification', 'Уведомление о заказе'),
        ('reminder', 'Напоминание'),
        ('confirmation', 'Подтверждение'),
        ('invoice_request', 'Запрос инвойса'),
    ]
    
    LANGUAGE_CHOICES = [
        ('', 'Все языки'),
        ('ru', 'Русский'),
        ('en', 'English'),
        ('de', 'Deutsch'),
        ('it', 'Italiano'),
        ('tr', 'Türkçe'),
        ('pl', 'Polski'),
        ('cz', 'Čeština'),
        ('cn', '中文'),
        ('lt', 'Lietuvių'),
    ]
    
    search = forms.CharField(
        required=False,
        label='Поиск',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Поиск по названию или описанию...'
        })
    )
    template_type = forms.ChoiceField(
        choices=SEARCH_CHOICES,
        required=False,
        label='Тип шаблона',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    language = forms.ChoiceField(
        choices=LANGUAGE_CHOICES,
        required=False,
        label='Язык',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_active = forms.BooleanField(
        required=False,
        label='Только активные',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    is_default = forms.BooleanField(
        required=False,
        label='Только по умолчанию',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
