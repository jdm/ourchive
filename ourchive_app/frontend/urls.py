from django.urls import path
from . import views
from django.conf.urls.static import static
from django.conf import settings
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index),
    path('search/', views.search),
    path('search/filter', views.search_filter),
    path('works/', views.works),
    path('works/new/', views.new_work),
    path('works/<int:id>/edit/', views.edit_work, name='edit-work'),
    path('works/<int:id>/publish/', views.publish_work, name='publish-work'),
    path('works/<int:id>/publish-full/', views.publish_work_and_chapters, name='publish-full'),
    path('works/<int:pk>/export/<str:file_ext>', views.export_work, name='export-work'),
    path('works/type/<int:type_id>', views.works_by_type),
    path('works/<int:pk>/', views.work),
    path('works/<int:work_id>/delete', views.delete_work, name='delete-work'),
    path('works/<int:work_id>/chapters/<int:chapter_id>/delete', views.delete_chapter, name='delete-chapter'),
    path('works/<int:work_id>/chapters/<int:chapter_id>/publish/', views.publish_chapter),
    path('bookmark-collections/', views.bookmark_collections),
    path('bookmark-collections/new', views.new_bookmark_collection),
    path('bookmark-collections/<int:pk>/edit', views.edit_bookmark_collection),
    path('bookmark-collections/<int:pk>/', views.bookmark_collection),
    path('bookmark-collections/<int:pk>/delete', views.delete_bookmark_collection, name='delete-bookmark-collection'),
    path('bookmark-collections/<int:pk>/publish', views.publish_bookmark_collection, name='publish-bookmark-collection'),
    path('bookmarks/', views.bookmarks),
    path('bookmarks/<int:pk>/', views.bookmark),
    path('bookmarks/<int:pk>/comments', views.render_bookmark_comments),
    path('bookmarks/<int:pk>/comments/new', views.create_bookmark_comment),
    path('bookmarks/<int:pk>/comments/edit', views.edit_bookmark_comment),
    path('bookmarks/<int:pk>/comments/<int:comment_id>/delete', views.delete_bookmark_comment, name='delete-bookmark-comment'),
    path('bookmarks/<int:pk>/edit', views.edit_bookmark),
    path('bookmarks/<int:id>/publish/', views.publish_bookmark),
    path('bookmarks/<int:bookmark_id>/delete', views.delete_bookmark, name='delete-bookmark'),
    path('bookmarks/new/<int:work_id>', views.new_bookmark),
    path('login/', views.log_in),
    path('register/', views.register),
    path('request-invite/', views.request_invite),
    path('logout/', views.log_out),
    path('reset-password/', auth_views.PasswordResetView.as_view(template_name="reset_password.html")),
    path('reset-password/done/', auth_views.PasswordResetDoneView.as_view(template_name="reset_password_done.html"), name='password_reset_done'),
    path('reset-password/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="reset_password_confirm.html"), name='password_reset_confirm'),
    path('reset-password/complete/', auth_views.PasswordResetCompleteView.as_view(template_name="reset_password_complete.html"), name='password_reset_complete'),
    path('change-password/', auth_views.PasswordChangeView.as_view(template_name="change_password.html"), name='password_change'),
    path('change-password/done/', auth_views.PasswordChangeDoneView.as_view(template_name="change_password_done.html"), name='password_change_done'),
    path('username/<str:username>/', views.user_name),
    path('username/<str:username>/edit', views.edit_user),
    path('username/<str:username>/account/edit', views.edit_account),
    path('username/<str:username>/works/', views.user_works),
    path('username/<str:username>/works/drafts/', views.user_works_drafts),
    path('username/<str:username>/bookmarks/', views.user_bookmarks),
    path('username/<str:username>/bookmark-collections/', views.user_bookmark_collections),
    path('username/<str:username>/bookmarks/drafts/', views.user_bookmarks_drafts),
    path('username/<str:username>/notifications/', views.user_notifications),
    path('username/<str:username>/notifications/<int:notification_id>/read', views.mark_notification_read),
    path('username/<str:username>/notifications/<int:notification_id>/delete', views.delete_notification),
    path('users/<str:username>/blocklist', views.user_block_list),
    path('users/<str:username>/blocks/<int:pk>/unblock', views.unblock_user),
    path('users/<str:username>/block', views.block_user),
    path('users/<str:username>/delete', views.delete_user),
    path('users/<str:username>/report', views.report_user, name='report-user'),
    path('works/<int:work_id>/chapters/<int:id>/edit', views.edit_chapter),
    path('works/<int:work_id>/chapters/new', views.new_chapter),
    path('works/<int:work_id>/chapters/<int:chapter_id>/comments', views.render_comments),
    path('works/<int:work_id>/chapters/<int:chapter_id>/comments/new', views.create_chapter_comment),
    path('works/<int:work_id>/chapters/<int:chapter_id>/comments/edit', views.edit_chapter_comment),
    path('works/<int:work_id>/chapters/<int:chapter_id>/comments/<int:comment_id>/delete', views.delete_chapter_comment, name='delete-chapter-comment'),
    path('tags/<int:pk>', views.works_by_tag),
    path('tags/<int:tag_id>/next', views.works_by_tag_next),
    path('fingerguns/<int:work_id>', views.new_fingerguns),
    path('switch-css-mode/', views.switch_css_mode, name='switch-css-mode'),
    path('tag-autocomplete', views.tag_autocomplete),
    path('bookmark-autocomplete', views.bookmark_autocomplete),
    path('content-pages/<int:pk>', views.content_page),
    path('accept-cookies', views.accept_cookies, name='accept-cookies'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
