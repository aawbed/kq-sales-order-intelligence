from django import forms

from inventory.models import Product, Stock


class StockAdjustmentForm(forms.Form):
    offset = forms.IntegerField(
        label="Adjustment Offset (+ / -)",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g. +38 or -10"}),
    )
    reason = forms.ChoiceField(
        label="Reason for Adjustment",
        choices=[
            ("delivery", "Received New Shipment Delivery"),
            ("correction", "Inventory Count Correction"),
            ("damage", "Damaged / Written Off"),
            ("dispatch", "Dispatched for Order Fulfilment"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "unit_price"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Heavy Duty Cargo Pallets"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
        }

    def clean_unit_price(self):
        price = self.cleaned_data.get("unit_price")
        if price is not None and price <= 0:
            raise forms.ValidationError("Unit price must be greater than zero.")
        return price