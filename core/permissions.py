"""
Role-based access control helpers.

Maps each of the four actors identified in the Use Case Diagram
(Figure 3.2) to the views/screens they are permitted to access,
enforcing the role-scoped navigation shown in the wireframes.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from accounts.models import Role


def role_required(*role_names):
    """
    View decorator restricting access to users whose Role.role_name
    is in role_names. Use like:

        @role_required(Role.RoleName.SALES_AGENT)
        def create_order_view(request): ...
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            user_role = getattr(request.user, "role", None)
            if user_role is None or user_role.role_name not in role_names:
                raise PermissionDenied("You do not have access to this screen.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


# Convenience decorators per role, mirroring the wireframes' role-scoped sidebars
sales_agent_required = role_required(Role.RoleName.SALES_AGENT)
warehouse_officer_required = role_required(Role.RoleName.WAREHOUSE_OFFICER)
operations_manager_required = role_required(Role.RoleName.OPERATIONS_MANAGER)
system_administrator_required = role_required(Role.RoleName.SYSTEM_ADMINISTRATOR)
