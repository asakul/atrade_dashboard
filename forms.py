from django import forms

class NewTradeForm(forms.Form):
    timestamp = forms.DateTimeField()
    account = forms.CharField(max_length=256)
    security = forms.CharField(max_length=256)
    operation = forms.ChoiceField(choices=[('buy', 'Buy'), ('sell', 'Sell')])
    price = forms.DecimalField()
    quantity = forms.IntegerField()
    volume = forms.DateField()
    volumeCurrency = forms.CharField(max_length=10)
    strategyId = forms.CharField(max_length=64)
    signalId = forms.CharField(max_length=64)

