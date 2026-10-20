from django import forms
from django.contrib.auth.forms import UserCreationForm

from accounts.models import Role, User


class SystemUserCreationForm(UserCreationForm):
    """
    Form for System Administrators / Operations Managers to create
    new staff accounts with a pre-assigned role.
    """

    first_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. James",
        }),
    )
    last_name = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. Mwangi",
        }),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. j.mwangi@kq.com",
        }),
    )
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        empty_label="Select a role...",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "password1", "password2"]
        widgets = {
            "username": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. jmwangi",
            }),
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_user = current_user
        is_admin = bool(
            current_user is None
            or getattr(current_user, "is_superuser", False)
            or (
                getattr(current_user, "role", None) is not None
                and current_user.role.role_name == Role.RoleName.SYSTEM_ADMINISTRATOR
            )
        )
        if not is_admin:
            self.fields["role"].queryset = Role.objects.exclude(
                role_name=Role.RoleName.SYSTEM_ADMINISTRATOR
            )
        self.fields["password1"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Set a secure password",
        })
        self.fields["password2"].widget.attrs.update({
            "class": "form-control",
            "placeholder": "Confirm the password",
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data["role"]
        if commit:
            user.save()
        return user
