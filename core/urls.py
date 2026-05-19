from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('about/', views.about, name='about'),
    path('committee/', views.committee_page, name='committee'),
    path('members/', views.member_directory, name='member_directory'),
    path('members/<int:user_id>/', views.member_profile, name='member_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('post/<int:post_id>/like/', views.like_post, name='like_post'),
    path('post/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('announcements/', views.announcements_page, name='announcements'),
]


# cbsf_cuet/
# ├── cbsf_cuet/                  # Project settings
# │   ├── __init__.py
# │   ├── settings.py
# │   ├── urls.py
# │   └── wsgi.py
# ├── apps/
# │   └── core/                   # Main application
# │       ├── __init__.py
# │       ├── admin.py
# │       ├── apps.py
# │       ├── forms.py
# │       ├── models.py
# │       ├── urls.py
# │       ├── views.py
# │       ├── templatetags/
# │       │   ├── __init__.py
# │       │   └── custom_filters.py
# │       ├── migrations/
# │       │   └── __init__.py
# │       ├── static/
# │       │   └── core/
# │       │       ├── css/
# │       │       │   └── style.css
# │       │       └── js/
# │       │           └── main.js
# │       └── templates/
# │           └── core/
# │               ├── base.html
# │               ├── homepage.html
# │               ├── about.html
# │               ├── committee.html
# │               ├── member_directory.html
# │               ├── member_profile.html
# │               ├── register.html
# │               ├── login.html
# │               ├── dashboard.html
# │               └── announcements.html
# ├── media/                      # User uploaded files
# ├── static/                     # Global static files
# ├── db.sqlite3
# ├── manage.py
# └── requirements.txt



