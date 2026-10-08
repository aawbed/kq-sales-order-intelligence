from django import forms
from django.forms import inlineformset_factory

from inventory.models import Product
from orders.models import Customer, Order, OrderItem, Payment


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "contact_info", "account_type"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Nairobi Logistics Hub",
            }),
            "contact_info": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Email or phone number",
            }),
            "account_type": forms.Select(
                choices=[
                    ("", "Select account type..."),
                    ("Corporate", "Corporate"),
                    ("Government", "Government"),
                    ("Distributor", "Distributor"),
                    ("Internal Department", "Internal Department"),
                ],
                attrs={"class": "form-select"},
            ),
        }


class OrderForm(forms.ModelForm):
    """Select a customer for a new order."""

    class Meta:
        model = Order
        fields = ["customer"]
        widgets = {
            "customer": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.all()
        self.fields["customer"].empty_label = "Select a customer..."


class OrderItemForm(forms.ModelForm):
    """A single line item in an order."""

    class Meta:
        model = OrderItem
        fields = ["product", "quantity"]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "quantity": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1",
                "placeholder": "Qty",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.all()
        self.fields["product"].empty_label = "Select product..."

    def save(self, commit=True):
        item = super().save(commit=False)
        # Auto-fill unit_price from the product's current price
        if item.product_id:
            item.unit_price = item.product.unit_price
        if commit:
            item.save()
        return item


# Inline formset: lets us handle multiple order items on the same page
OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemForm,
    extra=1,
    can_delete=True,
)


class PaymentForm(forms.ModelForm):
    """Record a payment against an invoice with validation against invoice balance."""

    class Meta:
        model = Payment
        fields = ["amount", "method", "reference", "payment_date", "notes"]
        widgets = {
            "amount": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0.01",
                "placeholder": "Amount in KSh",
            }),
            "method": forms.Select(attrs={"class": "form-select"}),
            "reference": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. M-Pesa code, Cheque #, or Journal Ref",
            }),
            "payment_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date",
            }),
            "notes": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Optional remarks",
            }),
        }

    def __init__(self, *args, invoice=None, **kwargs):
        self.invoice = invoice
        super().__init__(*args, **kwargs)
        if invoice and "amount" not in self.initial:
            self.initial["amount"] = invoice.balance
        from django.utils import timezone
        if "payment_date" not in self.initial:
            self.initial["payment_date"] = timezone.now().date()
        self.fields["payment_date"].required = False

    def clean_payment_date(self):
        p_date = self.cleaned_data.get("payment_date")
        if not p_date:
            from django.utils import timezone
            return timezone.now().date()
        return p_date

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if not amount or amount <= 0:
            raise forms.ValidationError("Payment amount must be greater than zero.")
        if self.invoice is not None:
            balance = self.invoice.balance
            if amount > balance:
                raise forms.ValidationError(
                    f"Payment amount (KSh {amount:,.2f}) cannot exceed the outstanding balance (KSh {balance:,.2f})."
                )
        return amount
