from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views, api_views, messaging_views, manage_views

app_name = 'core'

router = DefaultRouter()
router.register(r'gallery', api_views.PhotoGalleryViewSet, basename='api_gallery')
router.register(r'events', api_views.EventViewSet, basename='api_events')
router.register(r'posts', api_views.PostViewSet, basename='api_posts')

api_urlpatterns = [
    path('auth/register/', api_views.RegisterAPIView.as_view(), name='api_register'),
    path('auth/token/', api_views.ActiveMemberTokenObtainPairView.as_view(), name='token_obtain_pair'),
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
    path('admin-gallery/', views.admin_gallery_view, name='admin_gallery'),
    path('admin-gallery/<int:photo_id>/delete/', views.delete_gallery_photo, name='delete_gallery_photo'),
    path('profile/', views.view_profile, name='view_profile'),
    path('profile/edit/', views.update_profile, name='update_profile'),
    path('profile/switch-to-alumni/', views.switch_to_alumni, name='switch_to_alumni'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('post/<int:post_id>/like/', views.like_post, name='like_post'),
    path('post/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('announcements/', views.announcements_page, name='announcements'),
    path('events/', views.events_list, name='events'),
    path('events/<int:event_id>/', views.event_detail, name='event_detail'),
    path('events/<int:event_id>/rsvp/', views.event_rsvp, name='event_rsvp'),
    path('post/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('reply/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
    path('reply/<int:comment_id>/edit/', views.edit_comment, name='edit_comment'),
    path('post/<int:post_id>/pin/', views.toggle_pin, name='toggle_pin'),
    path('report/', views.report_content, name='report_content'),
    path('notifications/', views.notifications, name='notifications'),
    path('manage/', views.moderation, name='moderation'),
    path('manage/member/<int:user_id>/', manage_views.member_action, name='moderate_member'),
    path('manage/members/', manage_views.members, name='manage_members'),
    path('manage/events/', manage_views.events, name='manage_events'),
    path('manage/events/new/', manage_views.event_edit, name='manage_event_new'),
    path('manage/events/<int:event_id>/', manage_views.event_edit, name='manage_event_edit'),
    path('manage/events/<int:event_id>/delete/', manage_views.event_delete, name='manage_event_delete'),
    path('manage/events/<int:event_id>/attendees.csv', manage_views.event_attendees_csv, name='manage_event_csv'),
    path('manage/notices/', manage_views.notices, name='manage_notices'),
    path('manage/notices/new/', manage_views.notice_edit, name='manage_notice_new'),
    path('manage/notices/<int:notice_id>/', manage_views.notice_edit, name='manage_notice_edit'),
    path('manage/notices/<int:notice_id>/delete/', manage_views.notice_delete, name='manage_notice_delete'),
    path('manage/committee/', manage_views.committee, name='manage_committee'),
    path('manage/committee/<int:member_id>/', manage_views.committee, name='manage_committee_edit'),
    path('manage/committee/<int:member_id>/action/', manage_views.committee_action, name='manage_committee_action'),
    path('manage/committee/archive/', manage_views.committee_archive_session, name='manage_committee_archive'),
    path('manage/gallery/<int:photo_id>/feature/', manage_views.photo_feature, name='manage_photo_feature'),
    path('manage/report/<int:report_id>/', views.resolve_report, name='resolve_report'),
    path('guidelines/', views.guidelines, name='guidelines'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('healthz/', views.healthz, name='healthz'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    # Messaging
    path('inbox/', messaging_views.inbox, name='inbox'),
    path('messages/unread/', messaging_views.unread_status, name='messages_unread'),
    path('messages/search/', messaging_views.search_members, name='messages_search'),
    path('messages/<int:user_id>/', messaging_views.conversation, name='conversation'),
    path('messages/<int:user_id>/poll/', messaging_views.poll, name='conversation_poll'),
    path('messages/<int:user_id>/block/', messaging_views.toggle_block, name='toggle_block'),
    path('send-message/<int:user_id>/', messaging_views.send_message, name='send_message'),
    path('inbox/message/<int:message_id>/', messaging_views.view_message, name='view_message'),
    path('message/<int:message_id>/reply/', messaging_views.reply_message, name='reply_message'),
    path('advisory-panel/', views.advisory_panel, name='advisory_panel'),
    path('api/', include(api_urlpatterns)),
]
