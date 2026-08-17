from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views, api_views

app_name = 'core'

router = DefaultRouter()
router.register(r'gallery', api_views.PhotoGalleryViewSet, basename='api_gallery')
router.register(r'events', api_views.EventViewSet, basename='api_events')
router.register(r'posts', api_views.PostViewSet, basename='api_posts')

api_urlpatterns = [
    path('auth/register/', api_views.RegisterAPIView.as_view(), name='api_register'),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/me/', api_views.CurrentProfileAPIView.as_view(), name='api_current_profile'),
    path('admin/users/<int:user_id>/role/', api_views.AdminUserRoleAPIView.as_view(), name='api_admin_update_user_role'),
    path('alumni/', api_views.AlumniDirectoryAPIView.as_view(), name='api_alumni_directory'),
    path('committee/', api_views.CommitteeDirectoryAPIView.as_view(), name='api_committee_directory'),
    path('', include(router.urls)),
]

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('about/', views.about, name='about'),
    path('committee/', views.committee_page, name='committee'),
    path('committee-directory/', views.committee_directory, name='committee_directory'),
    path('members/', views.member_directory, name='member_directory'),
    path('members/<int:user_id>/', views.member_profile, name='member_profile'),
    path('alumni/', views.alumni_directory, name='alumni_directory'),
    path('gallery/', views.gallery_view, name='gallery'),
    path('admin/gallery/', views.admin_gallery_view, name='admin_gallery'),
    path('admin/gallery/<int:photo_id>/delete/', views.delete_gallery_photo, name='delete_gallery_photo'),
    path('profile/', views.view_profile, name='view_profile'),
    path('profile/edit/', views.update_profile, name='update_profile'),
    path('profile/switch-to-alumni/', views.switch_to_alumni, name='switch_to_alumni'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('post/<int:post_id>/like/', views.like_post, name='like_post'),
    path('post/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('announcements/', views.announcements_page, name='announcements'),
    path('events/', views.events_list, name='events'),
    path('events/<int:event_id>/', views.event_detail, name='event_detail'),
    path('post/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('inbox/', views.inbox, name='inbox'),
    path('inbox/message/<int:message_id>/', views.view_message, name='view_message'),
    path('send-message/<int:user_id>/', views.send_message, name='send_message'),
    path('message/<int:message_id>/reply/', views.reply_message, name='reply_message'),
    path('advisory-panel/', views.advisory_panel, name='advisory_panel'),
    path('api/', include(api_urlpatterns)),
]
