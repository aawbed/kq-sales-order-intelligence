import logging
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Avg

from accounts.models import Role
from analytics.models import SystemSetting
from core.models import Notification

logger = logging.getLogger(__name__)


def trigger_low_stock_alert(stock):
    """
    Checks stock levels against reorder threshold and dispatches in-app notifications
    to Warehouse Officers and Operations Managers if enabled in System Settings.
    """
    try:
        system_cfg = SystemSetting.get_settings()
        if not system_cfg.stock_alerts_warehouse:
            return 0

        if stock.quantity_on_hand <= stock.reorder_level:
            # Prevent duplicate unread notifications for the same product
            unread_exists = Notification.objects.filter(
                category=Notification.Category.LOW_STOCK,
                is_read=False,
                message__contains=stock.product.name,
            ).exists()

            if not unread_exists:
                level = (
                    Notification.Level.DANGER
                    if stock.quantity_on_hand == 0
                    else Notification.Level.WARNING
                )
                title = f"Low Stock Alert: {stock.product.name}"
                message = (
                    f"Inventory alert: {stock.product.name} is at {stock.quantity_on_hand} units "
                    f"on hand, reaching or below the reorder threshold ({stock.reorder_level} units)."
                )
                link = "/inventory/stock/"

                c1 = Notification.notify_role(
                    role_name=Role.RoleName.WAREHOUSE_OFFICER,
                    title=title,
                    message=message,
                    category=Notification.Category.LOW_STOCK,
                    level=level,
                    link=link,
                )
                c2 = Notification.notify_role(
                    role_name=Role.RoleName.OPERATIONS_MANAGER,
                    title=title,
                    message=message,
                    category=Notification.Category.LOW_STOCK,
                    level=level,
                    link=link,
                )
                return c1 + c2
    except Exception as exc:
        logger.warning("Error triggering low-stock alert: %s", exc)
    return 0


def check_and_alert_anomaly(order):
    """
    Evaluates a new or modified order against ML anomaly detection criteria and
    dispatches an in-app alert + email to Operations Managers if flagged.
    """
    try:
        system_cfg = SystemSetting.get_settings()

        items = order.items.all()
        if not items.exists():
            return False

        total_qty = sum(i.quantity for i in items)
        total_val = sum(i.quantity * i.unit_price for i in items)

        # Baseline comparisons
        from orders.models import OrderItem
        avg_stats = OrderItem.objects.aggregate(avg_qty=Avg("quantity"))
        avg_qty = avg_stats.get("avg_qty") or 50

        is_anomaly = False
        reasons = []

        # Criterion 1: Order volume significantly exceeds historical average (3.5x)
        if total_qty > avg_qty * 3.5:
            is_anomaly = True
            reasons.append(f"Volume of {total_qty} units is 3.5x higher than historical mean ({avg_qty:.0f} units)")

        # Criterion 2: Transaction value exceeds high single-order threshold (KES 200,000)
        if float(total_val) >= 200000.0:
            is_anomaly = True
            reasons.append(f"High-value booking total of KSh {float(total_val):,.2f}")

        # Criterion 3: Isolation Forest check if enough orders exist
        try:
            from analytics.ml.anomaly_detection import detect_anomalies
            from orders.models import Order
            all_orders = Order.objects.filter(pk=order.pk) | Order.objects.all()[:40]
            anomalies = detect_anomalies(all_orders, contamination=system_cfg.anomaly_contamination)
            for a in anomalies:
                if a.get("order_id") == order.order_id and a.get("is_anomaly"):
                    is_anomaly = True
                    reasons.append(f"Isolation Forest flagged anomaly (Score: {a.get('anomaly_score', 0):.3f})")
                    break
        except Exception:
            pass

        if is_anomaly:
            reason_str = " &bull; ".join(reasons) if reasons else "Unusual order pattern detected."
            title = f"ML Anomaly Flagged: Order KQ-{order.order_id}"
            message = (
                f"Order KQ-{order.order_id} for {order.customer.name} ({order.customer.account_type}) "
                f"was flagged by ML anomaly detection: {reason_str}"
            )
            link = f"/orders/{order.order_id}/"

            Notification.notify_role(
                role_name=Role.RoleName.OPERATIONS_MANAGER,
                title=title,
                message=message,
                category=Notification.Category.ANOMALY,
                level=Notification.Level.DANGER,
                link=link,
            )

            # Optional email dispatch if enabled
            if system_cfg.email_alerts_anomaly:
                try:
                    send_mail(
                        subject=f"[KQ Intelligence ALERT] ML Anomaly Detected: Order KQ-{order.order_id}",
                        message=(
                            f"Anomalous booking pattern detected for Kenya Airways Water Sales.\n\n"
                            f"Order: KQ-{order.order_id}\n"
                            f"Customer: {order.customer.name} ({order.customer.account_type})\n"
                            f"Total Quantity: {total_qty} units\n"
                            f"Total Value: KSh {float(total_val):,.2f}\n"
                            f"Flagged Reasons: {', '.join(reasons)}\n\n"
                            f"Please review this order in the Operations Dashboard:\n"
                            f"/orders/{order.order_id}/\n"
                        ),
                        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "alerts@kenya-airways.com"),
                        recipient_list=["operations@kenya-airways.com"],
                        fail_silently=True,
                    )
                except Exception as mail_exc:
                    logger.warning("Could not dispatch anomaly email: %s", mail_exc)

            return True
    except Exception as exc:
        logger.warning("Error evaluating order anomaly: %s", exc)
    return False
