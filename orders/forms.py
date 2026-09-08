from django import forms

from orders.models import Customer


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
