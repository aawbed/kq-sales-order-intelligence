from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.Model):
    """
    Corresponds to the ROLE entity in the ERD / class diagram.
    Determines a user's access permissions across the system
    (Sales Agent, Warehouse Officer, Operations Manager, System Administrator).
    """

    class RoleName(models.TextChoices):
        SALES_AGENT = "sales_agent", "Sales Agent"
        WAREHOUSE_OFFICER = "warehouse_officer", "Warehouse Officer"
        OPERATIONS_MANAGER = "operations_manager", "Operations Manager"
        SYSTEM_ADMINISTRATOR = "system_administrator", "System Administrator"

    role_id = models.AutoField(primary_key=True)
    role_name = models.CharField(max_length=30, choices=RoleName.choices, unique=True)
    permissions = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.get_role_name_display()


class User(AbstractUser):
    """
    Corresponds to the USER entity in the ERD / class diagram.
    Extends Django's built-in auth user so password hashing, login,
    and session handling are inherited rather than re-implemented.
    """

    user_id = models.AutoField(primary_key=True)
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, related_name="users", null=True, blank=True
    )

    def __str__(self):
        return self.username
