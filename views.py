
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template import loader
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.db import transaction

from .models import RobotInstance, Trade, ClosedTrade
from .forms import NewTradeForm, ClosedTradeFilterForm
import redis
import json
import datetime

def overview(request):
    r = redis.StrictRedis(unix_socket_path='/var/run/redis/redis')
    robot_instances = RobotInstance.objects.order_by('instanceId')
    robot_states = []
    index = 0
    for robot in robot_instances:
        entry = {}
        entry['positions'] = dict()
        raw_state = r.get(robot.instanceId)
        if raw_state is not None:
            state = json.loads(str(raw_state, 'utf-8'))
            try:
                entry['positions'] = state['positions']
                del state['positions']
            except KeyError:
                entry['positions'] = dict()
        else:
            state = dict()

        open_pos_counter = 0
        pending_pos_counter = 0
        for pos in entry['positions']:
            if pos['posState']['tag'] == 'PositionOpen':
                open_pos_counter += 1
            elif pos['posState']['tag'] == 'PositionWaitingOpen':
                pending_pos_counter += 1

        entry['open_pos_counter'] = open_pos_counter
        entry['pending_pos_counter'] = pending_pos_counter
        entry['state'] = json.dumps(state, sort_keys=True, indent=2, separators=(',', ': '))

        last_store = r.get(robot.instanceId + ":last_store")
        if last_store is not None:
            entry['last_store'] = datetime.datetime.utcfromtimestamp(float(str(last_store, 'utf-8')[:-1]))
        index += 1
        entry['index'] = index
        entry['instance_id'] = robot.instanceId

        robot_states.append(entry)

    template = loader.get_template('dashboard/overview.html')
    context = {
            'robot_instances' : robot_instances,
            'robot_states' : robot_states
            }
    return HttpResponse(template.render(context, request))

def add_instance(request):
    instance_id = request.POST['instance_id']
    if instance_id == "" or RobotInstance.objects.filter(instanceId=instance_id).count() > 0:
        messages.error(request, 'Invalid instance ID specified')
    else:
        new_instance = RobotInstance(instanceId=instance_id)
        new_instance.save()
    return HttpResponseRedirect(reverse('overview'))

def delete_instance(request, instance_id):
    instance = get_object_or_404(RobotInstance, instanceId=instance_id)
    instance.delete()
    return HttpResponseRedirect(reverse('overview'))

def trades_index(request):
    now = datetime.datetime.utcnow()
    new_trade_form = NewTradeForm(initial={'timestamp' : now})
    trades = Trade.objects.all().order_by('-timestamp')
    template = loader.get_template('dashboard/trades.html')
    context = {
            'trades' : trades,
            'new_trade_form' : new_trade_form
            }
    return HttpResponse(template.render(context, request))

def delete_trade(request, trade_id):
    trade = get_object_or_404(Trade, pk=trade_id)
    trade.delete()
    return HttpResponseRedirect(reverse('trades_index'))

def add_trade(request):
    if request.method == 'POST':
        form = NewTradeForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            quantity_multiplier = 1
            if d['operation'] == 'sell':
                quantity_multiplier = -1
            trade = Trade(account=d['account'], security=d['security'], price=d['price'], quantity=quantity_multiplier * d['quantity'],
                    volume=d['volume'], volumeCurrency=d['volumeCurrency'], strategyId=d['strategyId'], signalId=d['signalId'], timestamp=d['timestamp'], balanced=False)
            trade.save()
            return HttpResponseRedirect(reverse('trades_index'))
        else:
            trades = Trade.objects.all()
            template = loader.get_template('dashboard/trades.html')
            context = {
                    'trades' : trades,
                    'new_trade_form' : form
                    }
            return HttpResponse(template.render(context, request))
    raise Http404("Invalid method")

@transaction.atomic
def aggregate_unbalanced_trades():
    unbalanced_trades = Trade.objects.filter(balanced=False).order_by('timestamp')
    balanced_trades = []
    balances = {}
    for trade in unbalanced_trades:
        balance_key = '/'.join([trade.account, trade.security, trade.strategyId])
        try:
            balance_entry = balances[balance_key]
        except KeyError:
            balance_entry = { 'balance' : 0}

        print('ts:', trade.timestamp)
        if balance_entry['balance'] == 0:
            print('new entry: ', balance_key)
            balance_entry['balance'] = trade.quantity
            direction = ''
            if trade.quantity > 0:
                direction='long'
            else:
                direction='short'
            balance_entry['trade'] = ClosedTrade(account=trade.account, security=trade.security, entryTime=trade.timestamp, profitCurrency=trade.volumeCurrency,
                    profit=(-trade.price * trade.quantity), strategyId=trade.strategyId, direction=direction)
            balance_entry['ks'] = trade.volume / (trade.price * abs(trade.quantity))
            balance_entry['trade_ids'] = [trade.pk]
        else:
            print('update entry: ', balance_key)
            balance_entry['balance'] += trade.quantity
            balance_entry['trade'].profit += -trade.price * trade.quantity
            balance_entry['ks'] += trade.volume / (trade.price * abs(trade.quantity))
            balance_entry['ks'] /= 2
            balance_entry['trade_ids'].append(trade.pk)
            
            print('updated: ', balance_entry['balance'])
            if balance_entry['balance'] == 0:
                balance_entry['trade'].profit *= balance_entry['ks']
                balance_entry['trade'].exitTime = trade.timestamp
                balanced_trades.append((balance_entry['trade'], balance_entry['trade_ids']))
        balances[balance_key] = balance_entry

    for trade, trade_ids in balanced_trades:
        trade.save()
        for trade_id in trade_ids:
            tr = Trade.objects.get(pk=trade_id)
            tr.balanced = True
            tr.save()

def make_cumulative_profits(closed_trades):
    result = {}
    for trade in closed_trades:
        try:
            result[trade.account]['value'] += trade.profit
        except KeyError:
            result[trade.account] = { 'name' : trade.account,
                    'value' : trade.profit,
                    'elements' : [] }

        element = {'year' : trade.exitTime.year,
                   'month' : trade.exitTime.month,
                   'day' : trade.exitTime.day,
                   'hour' : trade.exitTime.hour,
                   'minute' : trade.exitTime.minute,
                   'second' : trade.exitTime.second,
                   'value' : result[trade.account]['value']}
        result[trade.account]['elements'].append(element)
    return result

def closed_trades_index(request):
    aggregate_unbalanced_trades()
    form = ClosedTradeFilterForm(request.GET)
    if form.is_valid():
        d = form.cleaned_data
        if len(d['accounts']) == 0:
            if len(d['strategies']) == 0:
                closed_trades = ClosedTrade.objects.all()
            else:
                closed_trades = ClosedTrade.objects.filter(strategyId__in=list(d['strategies']))
        else:
            if len(d['strategies']) == 0:
                closed_trades = ClosedTrade.objects.filter(account__in=list(d['accounts']))
            else:
                closed_trades = ClosedTrade.objects.filter(account__in=list(d['accounts']), strategyId__in=list(d['strategies']))
    else:
        closed_trades = ClosedTrade.objects.all()
        form = ClosedTradeFilterForm()

    closed_trades = closed_trades.order_by('-entryTime')

    closed_trades_prime = closed_trades.order_by('exitTime')

    cum_profits = make_cumulative_profits(closed_trades_prime)

    template = loader.get_template('dashboard/closed_trades.html')
    context = {
            'closed_trades' : closed_trades,
            'closed_trades_filter_form' : form,
            'cumulative_profits' : cum_profits
            }
    return HttpResponse(template.render(context, request))

@transaction.atomic
def do_rebalance():
    ClosedTrade.objects.all().delete()
    Trade.objects.all().update(balanced=False)
    

def rebalance_closed_trades(request):
    do_rebalance()
    return HttpResponseRedirect(reverse('closed_trades_index'))
