from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Figure 3.7a: Login Screen
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Figure 3.7j: Manage User Accounts (Operations Manager / System Administrator)
    path("users/", views.manage_users, name="manage_users"),
    path("users/<int:user_id>/edit-role/", views.edit_user_role, name="edit_user_role"),
    path("users/<int:user_id>/toggle-active/", views.toggle_user_active, name="toggle_user_active"),
]
