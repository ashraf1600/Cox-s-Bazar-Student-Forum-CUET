from django.contrib import admin
from django.contrib.auth import views as auth_views
from core.forms import StyledPasswordResetForm, StyledSetPasswordForm
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="CSF-CUET API Documentation",
      default_version='v1',
      description="RESTful API documentation for Cox's Bazar Student Forum (CUET) platform",
      contact=openapi.Contact(email="admin@cuet.ac.bd"),
      license=openapi.License(name="MIT License"),
   ),
   public=settings.DEBUG,
   # API docs are open in development, admin-only in production.
   permission_classes=(permissions.AllowAny,) if settings.DEBUG else (permissions.IsAdminUser,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    # "Forgot password?" flow (Django's built-in views and templates)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='core/auth/password_reset_form.html', form_class=StyledPasswordResetForm), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='core/auth/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='core/auth/password_reset_confirm.html', form_class=StyledSetPasswordForm), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='core/auth/password_reset_complete.html'), name='password_reset_complete'),
    path('', include('core.urls')),
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
