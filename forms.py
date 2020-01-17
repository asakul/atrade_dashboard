from django import forms
from .models import ClosedTrade
import datetime

def get_all_accounts_and_strategies():
    all_accounts = set()
    all_strategies = set()
    for trade in ClosedTrade.objects.all():
        all_accounts.add(trade.account)
        all_strategies.add(trade.strategyId)
    return (all_accounts, all_strategies)

class LoginForm(forms.Form):
    username = forms.CharField(max_length=64)
    password = forms.CharField(widget=forms.PasswordInput)

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

class TradeFilterForm(forms.Form):
    def __init__(self, *args, show_unbalanced_checkbox=False, **kwargs):
        super().__init__(*args, **kwargs)

        now = datetime.date.today()
        
        all_accounts, all_strategies = get_all_accounts_and_strategies()
        self.fields['accounts'] = forms.MultipleChoiceField(choices=zip(sorted(list(all_accounts)), sorted(list(all_accounts))), required=False)
        self.fields['strategies'] = forms.MultipleChoiceField(choices=zip(sorted(list(all_strategies)), sorted(list(all_strategies))), required=False)
        self.fields['startdate'] = forms.DateField(initial=(now - datetime.timedelta(weeks=4)))
        self.fields['enddate'] = forms.DateField(initial=now)
        try:
            if show_unbalanced_checkbox:
                self.fields['unbalanced_only'] = forms.BooleanField(required=False)
        except KeyError:
            pass
