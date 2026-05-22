import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-cbsf-cuet-secret-key-change-in-production'

DEBUG = True

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'jazzmin', # Must be before 'django.contrib.admin'
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_forms',
    'crispy_bootstrap5',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'csf_cuet.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'csf_cuet.settings.unread_count',  # Custom context processor for unread message count
            ],
        },
    },
]

WSGI_APPLICATION = 'csf_cuet.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_USER_MODEL = 'core.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = 'core:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'core:homepage'
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# settings.py

# Example of JAZZMIN_SETTINGS (add this anywhere in your settings file)
JAZZMIN_SETTINGS = {
    # Title of the window (Will default to current_admin_site.site_title)
    "site_title": "CBSF-CUET Admin",
    
    # Title on the login screen (19 chars max)
    "site_header": "Cox's Bazar Student Forum",
    
    # Title on the brand (19 chars max)
    "site_brand": "CBSF-CUET Admin Portal",
    
    # Logo to use for your site, must be present in static files
    "site_logo": "admin/img/logo.png",  # You'll need to add this logo file
    "site_logo_classes": "img-circle",  # CSS classes applied to the logo
    
    # Welcome text on the login screen
    "welcome_sign": "Welcome to the CBSF-CUET Admin Panel",
    
    # Copyright on the footer
    "copyright": "Cox's Bazar Student Forum, CUET",
    
    # Whether to show the UI customizer on the sidebar (interactive customization)
    "show_ui_builder": True,  # Essential for easy theme tweaking[reference:2]
    
    # List of apps (and/or models) to base the side menu ordering on.
    "order_with_respect_to": ["auth", "core", "core.user", "core.post"],
    
    # Icons for side menu apps/models (using Font Awesome icons)[reference:3]
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.group": "fas fa-users",
        "core.User": "fas fa-user-circle",
        "core.Post": "fas fa-newspaper",
        "core.Comment": "fas fa-comments",
        "core.Announcement": "fas fa-bullhorn",
        "core.Department": "fas fa-building",
        "core.CommitteeMember": "fas fa-user-tie",
    },
    
    # UI tweaks for themes and layout
    "changeform_format": "horizontal_tabs",  # Options: 'horizontal_tabs', 'vertical_tabs', 'collapsible', 'carousel'
    "changeform_format_overrides": {"auth.user": "collapsible", "auth.group": "vertical_tabs"},
    
    # Add a search bar to the admin for specific models
    "search_model": ["core.User", "core.Post"],
}

# settings.py

JAZZMIN_SETTINGS = {
    # Title of the window (Will default to current_admin_site.site_title)
    "site_title": "CSF-CUET Admin",
    # Title on the login screen
    "site_header": "Cox's Bazar Student Forum, CUET ",
    # Title on the brand (19 chars max)
    "site_brand": "CSF-CUET Admin Portal",
    # Logo to use for your site, must be present in static files
    "site_logo": "admin/image/logo.png", # You'll need to add this logo file
    "site_logo_classes": "img-circle",
    # Welcome text on the login screen
    "welcome_sign": "Welcome to the CSF-CUET Admin Panel",
    # Copyright on the footer
    "copyright": "Cox's Bazar Student Forum, CUET",
    # Icons for side menu apps/models (using Font Awesome icons)
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "core.User": "fas fa-user-circle",
    },
    # Whether to aut expand the menu
    "navigation_expanded": True,
    # Hide these apps when generating side menu e.g (auth)
    "hide_apps": [],
    # List of apps to base side menu ordering off of
    "order_with_respect_to": ["auth", "core"],
}


def unread_count(request):
    if request.user.is_authenticated:
        from core.models import Message
        return {'unread_count': Message.objects.filter(recipient=request.user, is_read=False).count()}
    return {'unread_count': 0}