"""
Views for email template management.
"""

from typing import Dict, Any
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.http import JsonResponse, HttpResponse
from django.urls import reverse_lazy, reverse
from django.db.models import Q
from django.core.paginator import Paginator
from django.template import Template, Context
from django.utils import timezone

from ..models import EmailTemplate, EmailTemplateVersion
from ..email_forms import EmailTemplateForm, EmailTemplatePreviewForm, EmailTemplateSearchForm


@method_decorator(login_required, name='dispatch')
class EmailTemplateListView(ListView):
    """List view for email templates with search and filtering"""
    
    model = EmailTemplate
    template_name = 'orders/email_template_list.html'
    context_object_name = 'templates'
    paginate_by = 20
    
    def get_queryset(self):
        """Get filtered templates based on search parameters"""
        queryset = EmailTemplate.objects.all()
        
        # Get search parameters
        search = self.request.GET.get('search', '')
        template_type = self.request.GET.get('template_type', '')
        language = self.request.GET.get('language', '')
        is_active = self.request.GET.get('is_active')
        is_default = self.request.GET.get('is_default')
        
        # Apply filters
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(subject__icontains=search)
            )
        
        if template_type:
            queryset = queryset.filter(template_type=template_type)
        
        if language:
            queryset = queryset.filter(language=language)
        
        if is_active:
            queryset = queryset.filter(is_active=True)
        
        if is_default:
            queryset = queryset.filter(is_default=True)
        
        return queryset.order_by('template_type', 'language', 'name')
    
    def get_context_data(self, **kwargs):
        """Add search form to context"""
        # Устанавливаем необходимые атрибуты для ListView
        if not hasattr(self, 'kwargs'):
            self.kwargs = {}
        if not hasattr(self, 'object_list'):
            self.object_list = self.get_queryset()
        
        context = super().get_context_data(**kwargs)
        context['search_form'] = EmailTemplateSearchForm(self.request.GET)
        return context


@method_decorator(login_required, name='dispatch')
class EmailTemplateDetailView(DetailView):
    """Detail view for email template"""
    
    model = EmailTemplate
    template_name = 'orders/email_template_detail.html'
    context_object_name = 'template'
    
    def get_context_data(self, **kwargs):
        """Add additional context"""
        context = super().get_context_data(**kwargs)
        template = self.get_object()
        
        # Add available variables
        context['available_variables'] = template.get_available_variables()
        
        # Add preview form
        context['preview_form'] = EmailTemplatePreviewForm(initial={
            'template_id': template.pk
        })
        
        # Add versions
        context['versions'] = template.versions.all()[:10]  # Last 10 versions
        
        return context


@method_decorator(login_required, name='dispatch')
class EmailTemplateCreateView(CreateView):
    """Create view for email template"""
    
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = 'orders/email_template_form.html'
    
    def get_form_kwargs(self):
        """Add user to form kwargs"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        """Add additional context"""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Создать шаблон'
        context['submit_text'] = 'Создать шаблон'
        return context
    
    def form_valid(self, form):
        """Handle successful form submission"""
        response = super().form_valid(form)
        messages.success(self.request, f'Шаблон "{self.object.name}" успешно создан!')
        return response


@method_decorator(login_required, name='dispatch')
class EmailTemplateUpdateView(UpdateView):
    """Update view for email template"""
    
    model = EmailTemplate
    form_class = EmailTemplateForm
    template_name = 'orders/email_template_form.html'
    
    def get_form_kwargs(self):
        """Add user to form kwargs"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        """Add additional context"""
        context = super().get_context_data(**kwargs)
        context['title'] = 'Редактировать шаблон'
        context['submit_text'] = 'Сохранить изменения'
        return context
    
    def form_valid(self, form):
        """Handle successful form submission"""
        # Create version before saving
        template = self.get_object()
        if template.pk:
            # Create version
            version_number = template.versions.count() + 1
            EmailTemplateVersion.objects.create(
                template=template,
                version_number=version_number,
                subject=template.subject,
                html_content=template.html_content,
                text_content=template.text_content,
                change_description=f'Редактирование пользователем {self.request.user.username}',
                created_by=self.request.user
            )
        
        response = super().form_valid(form)
        messages.success(self.request, f'Шаблон "{self.object.name}" успешно обновлен!')
        return response


@method_decorator(login_required, name='dispatch')
class EmailTemplateDeleteView(DeleteView):
    """Delete view for email template"""
    
    model = EmailTemplate
    template_name = 'orders/email_template_confirm_delete.html'
    success_url = reverse_lazy('email_template_list')
    
    def delete(self, request, *args, **kwargs):
        """Handle template deletion"""
        template = self.get_object()
        template_name = template.name
        response = super().delete(request, *args, **kwargs)
        messages.success(request, f'Шаблон "{template_name}" успешно удален!')
        return response


@login_required
def email_template_preview(request, pk):
    """Preview email template with test data"""
    template = get_object_or_404(EmailTemplate, pk=pk)
    
    if request.method == 'POST':
        form = EmailTemplatePreviewForm(request.POST)
        if form.is_valid():
            try:
                # Get test context
                context = form.get_test_context()
                
                # Render template
                rendered = template.render_template(context)
                
                return JsonResponse({
                    'success': True,
                    'subject': rendered['subject'],
                    'html_content': rendered['html_content'],
                    'text_content': rendered['text_content']
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Неверные данные формы'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Метод не разрешен'
    })


@login_required
def email_template_duplicate(request, pk):
    """Duplicate email template"""
    template = get_object_or_404(EmailTemplate, pk=pk)
    
    # Create duplicate
    duplicate = EmailTemplate.objects.create(
        name=f"{template.name} (копия)",
        template_type=template.template_type,
        language=template.language,
        subject=template.subject,
        html_content=template.html_content,
        text_content=template.text_content,
        description=template.description,
        variables_help=template.variables_help,
        is_active=False,  # Неактивная копия
        is_default=False,  # Не по умолчанию
        created_by=request.user
    )
    
    messages.success(request, f'Шаблон "{template.name}" успешно скопирован!')
    return redirect('email_template_update', pk=duplicate.pk)


@login_required
def email_template_activate(request, pk):
    """Activate/deactivate email template"""
    template = get_object_or_404(EmailTemplate, pk=pk)
    
    template.is_active = not template.is_active
    template.save()
    
    status = 'активирован' if template.is_active else 'деактивирован'
    messages.success(request, f'Шаблон "{template.name}" {status}!')
    
    return redirect('email_template_detail', pk=pk)


@login_required
def email_template_set_default(request, pk):
    """Set template as default for its type and language"""
    template = get_object_or_404(EmailTemplate, pk=pk)
    
    # Remove default flag from other templates
    EmailTemplate.objects.filter(
        template_type=template.template_type,
        language=template.language,
        is_default=True
    ).update(is_default=False)
    
    # Set this template as default
    template.is_default = True
    template.save()
    
    messages.success(request, f'Шаблон "{template.name}" установлен как шаблон по умолчанию!')
    
    return redirect('email_template_detail', pk=pk)


@login_required
def email_template_export(request, pk):
    """Export email template as JSON"""
    template = get_object_or_404(EmailTemplate, pk=pk)
    
    data = {
        'name': template.name,
        'template_type': template.template_type,
        'language': template.language,
        'subject': template.subject,
        'html_content': template.html_content,
        'text_content': template.text_content,
        'description': template.description,
        'variables_help': template.variables_help,
        'exported_at': timezone.now().isoformat(),
        'exported_by': request.user.username
    }
    
    response = HttpResponse(
        content_type='application/json',
        headers={'Content-Disposition': f'attachment; filename="template_{template.pk}.json"'}
    )
    
    import json
    response.write(json.dumps(data, ensure_ascii=False, indent=2))
    
    return response


@login_required
def email_template_import(request):
    """Import email template from JSON"""
    if request.method == 'POST':
        try:
            import json
            
            # Get uploaded file
            uploaded_file = request.FILES.get('template_file')
            if not uploaded_file:
                messages.error(request, 'Файл не выбран!')
                return redirect('email_template_list')
            
            # Read and parse JSON
            content = uploaded_file.read().decode('utf-8')
            data = json.loads(content)
            
            # Create template
            template = EmailTemplate.objects.create(
                name=data.get('name', 'Импортированный шаблон'),
                template_type=data.get('template_type', 'factory_order'),
                language=data.get('language', 'ru'),
                subject=data.get('subject', ''),
                html_content=data.get('html_content', ''),
                text_content=data.get('text_content', ''),
                description=data.get('description', ''),
                variables_help=data.get('variables_help', ''),
                is_active=False,  # Неактивный импорт
                is_default=False,  # Не по умолчанию
                created_by=request.user
            )
            
            messages.success(request, f'Шаблон "{template.name}" успешно импортирован!')
            return redirect('email_template_detail', pk=template.pk)
            
        except Exception as e:
            messages.error(request, f'Ошибка импорта: {str(e)}')
            return redirect('email_template_list')
    
    return redirect('email_template_list')


@login_required
def email_template_variables_help(request):
    """Get available variables for templates"""
    variables = {
        'order': {
            'title': 'Название заказа',
            'description': 'Описание заказа',
            'uploaded_at': 'Дата заказа',
            'status': 'Статус заказа',
            'comments': 'Комментарии к заказу',
        },
        'factory': {
            'name': 'Название фабрики',
            'email': 'Email фабрики',
            'contact_person': 'Контактное лицо',
            'phone': 'Телефон фабрики',
            'address': 'Адрес фабрики',
        },
        'employee': {
            'get_full_name': 'Полное имя сотрудника',
            'username': 'Имя пользователя',
            'email': 'Email сотрудника',
        },
        'country': {
            'name': 'Название страны',
            'code': 'Код страны',
        }
    }
    
    return JsonResponse(variables)


@login_required
def email_template_preview_ajax(request):
    """AJAX endpoint for template preview"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method allowed'})
    
    try:
        # Получаем данные из формы
        subject = request.POST.get('subject', '')
        html_content = request.POST.get('html_content', '')
        text_content = request.POST.get('text_content', '')
        
        # Создаем тестовый контекст
        from django.utils import timezone
        test_context = {
            'order': type('Order', (), {
                'title': 'Тестовый заказ',
                'description': 'Описание тестового заказа',
                'uploaded_at': timezone.now(),
                'status': 'uploaded',
                'comments': 'Тестовые комментарии',
            })(),
            'factory': type('Factory', (), {
                'name': 'Тестовая фабрика',
                'email': 'test@factory.com',
                'contact_person': 'Иван Иванов',
                'phone': '+49 123 456 789',
                'address': 'Teststraße 123, 12345 Teststadt',
            })(),
            'employee': type('Employee', (), {
                'get_full_name': 'Петр Петров',
                'username': 'testuser',
                'email': 'test@company.com',
            })(),
            'country': type('Country', (), {
                'name': 'Германия',
                'code': 'DE',
            })(),
        }
        
        # Рендерим шаблоны
        from django.template import Template, Context
        
        rendered_subject = Template(subject).render(Context(test_context))
        rendered_html = Template(html_content).render(Context(test_context))
        rendered_text = Template(text_content).render(Context(test_context))
        
        return JsonResponse({
            'success': True,
            'subject': rendered_subject,
            'html_content': rendered_html,
            'text_content': rendered_text
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
