from django import forms
from .models import ClosedTrade

def get_all_accounts_and_strategies():
    all_accounts = set()
    all_strategies = set()
    for trade in ClosedTrade.objects.all():
        all_accounts.add(trade.account)
        all_strategies.add(trade.strategyId)
    return (all_accounts, all_strategies) 

class NewTradeForm(forms.Form):
    timestamp = forms.DateTimeField()
    account = forms.CharField(max_length=256)
    security = forms.CharField(max_length=256)
    operation = forms.ChoiceField(choices=[('buy', 'Buy'), ('sell', 'Sell')])
    price = forms.DecimalField()
    quantity = forms.IntegerField()
    volume = forms.DecimalField()
    volumeCurrency = forms.CharField(max_length=10)
    strategyId = forms.CharField(max_length=64)
    signalId = forms.CharField(max_length=64)

class ClosedTradeFilterForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        all_accounts, all_strategies = get_all_accounts_and_strategies()
        self.fields['accounts'] = forms.MultipleChoiceField(choices=zip(list(all_accounts), list(all_accounts)), required=False)
        self.fields['strategies'] = forms.MultipleChoiceField(choices=zip(list(all_strategies), list(all_strategies)), required=False)

