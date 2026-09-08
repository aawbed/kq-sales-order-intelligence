from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Figure 3.7a: Login Screen
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Figure 3.7j: Manage User Accounts (Operations Manager / System Administrator)
    path("users/", views.manage_users, name="manage_users"),
    path("users/<int:user_id>/edit-role/", views.edit_user_role, name="edit_user_role"),
]
