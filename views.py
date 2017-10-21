
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template import loader
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import RobotInstance, Trade, ClosedTrade
from .forms import NewTradeForm, ClosedTradeFilterForm, LoginForm
import redis
import json
import datetime
import calendar

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        nextlink = request.POST.get('next', '')
        if form.is_valid():
            username = request.POST['username']
            password = request.POST['password']
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                if nextlink == "":
                    return HttpResponseRedirect(reverse('overview'))
                else:
                    return HttpResponseRedirect(nextlink)
            else:
                return HttpResponseRedirect(reverse('login'))
        else:
            template = loader.get_template('dashboard/login.html')

            context = {
                    'login_form' : form,
                    'next' : nextlink
                    }
            return HttpResponse(template.render(context, request))
    else:
        form = LoginForm()
        template = loader.get_template('dashboard/login.html')
        nextlink = request.GET.get('next', '')
        context = {
                'login_form' : form,
                'next' : nextlink
                }
        return HttpResponse(template.render(context, request))
    raise Http404("Invalid method")

def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse('login'))

@login_required
def overview(request):
    r = redis.StrictRedis(unix_socket_path='/var/run/redis/redis')
    robot_instances = RobotInstance.objects.order_by('instanceId')
    robot_states = []
    index = 0
    for robot in robot_instances:
        try:
            raw_state = r.get(robot.instanceId)
            last_store = r.get(robot.instanceId + ":last_store")
        except:
            raw_state = b"{}"
            last_store = None

        entry = {}
        entry['positions'] = dict()
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

        if last_store is not None:
            entry['last_store'] = datetime.datetime.utcfromtimestamp(float(str(last_store, 'utf-8')[:-1]))
        index += 1
        entry['index'] = index
        entry['instance_id'] = robot.instanceId

        robot_states.append(entry)

    template = loader.get_template('dashboard/overview.html')
    context = {
            'robot_instances' : robot_instances,
            'robot_states' : robot_states,
            'user' : request.user
            }
    return HttpResponse(template.render(context, request))

@login_required
def add_instance(request):
    instance_id = request.POST['instance_id']
    if instance_id == "" or RobotInstance.objects.filter(instanceId=instance_id).count() > 0:
        messages.error(request, 'Invalid instance ID specified')
    else:
        new_instance = RobotInstance(instanceId=instance_id)
        new_instance.save()
    return HttpResponseRedirect(reverse('overview'))

@login_required
def delete_instance(request, instance_id):
    instance = get_object_or_404(RobotInstance, instanceId=instance_id)
    instance.delete()
    return HttpResponseRedirect(reverse('overview'))

@login_required
def trades_index(request):
    now = datetime.datetime.utcnow()
    new_trade_form = NewTradeForm(initial={'timestamp' : now})
    trades = Trade.objects.all().order_by('-timestamp')
    form_filter = ClosedTradeFilterForm(request.GET)
    if form_filter.is_valid():
        d = form_filter.cleaned_data
        if len(d['strategies']) > 0:
            trades = trades.filter(strategyId__in=list(d['strategies']))
        if len(d['accounts']) > 0:
            trades = trades.filter(account__in=list(d['accounts']))

        if d['startdate'] is not None:
            trades = trades.filter(timestamp__gte=d['startdate'])
        if d['enddate'] is not None:
            trades = trades.filter(timestamp__lte=d['enddate'])

    else:
        now = datetime.date.today()
        form_filter = ClosedTradeFilterForm()

    paginator = Paginator(trades, 25)
    try:
        page_num = int(request.GET.get('page'))
    except:
        page_num = 1
    try:
        trades = paginator.page(page_num)
    except PageNotAnInteger:
        trades = paginator.page(1)
    except EmptyPage:
        trades = paginator.page(1)


    template = loader.get_template('dashboard/trades.html')
    context = {
            'trades' : trades,
            'closed_trades_filter_form' : form_filter,
            'new_trade_form' : new_trade_form,
            'user' : request.user,
            'page_num' : page_num,
            'page_range' : paginator.page_range
            }
    return HttpResponse(template.render(context, request))

@login_required
def delete_trade(request, trade_id):
    trade = get_object_or_404(Trade, pk=trade_id)
    trade.delete()
    return HttpResponseRedirect(reverse('trades_index'))

@login_required
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
                    'new_trade_form' : form,
                    'user' : request.user
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
            balance_entry['commissions'] = trade.commission
        else:
            print('update entry: ', balance_key)
            balance_entry['balance'] += trade.quantity
            balance_entry['trade'].profit += -trade.price * trade.quantity
            balance_entry['ks'] += trade.volume / (trade.price * abs(trade.quantity))
            balance_entry['ks'] /= 2
            balance_entry['trade_ids'].append(trade.pk)
            balance_entry['commissions'] += trade.commission

            print('updated: ', balance_entry['balance'])
            if balance_entry['balance'] == 0:
                balance_entry['trade'].profit *= balance_entry['ks']
                balance_entry['trade'].profit -= balance_entry['commissions']
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
                   'month' : trade.exitTime.month - 1,
                   'day' : trade.exitTime.day,
                   'hour' : trade.exitTime.hour,
                   'minute' : trade.exitTime.minute,
                   'second' : trade.exitTime.second,
                   'value' : result[trade.account]['value']}
        result[trade.account]['elements'].append(element)
    return result

@login_required
def closed_trades_index(request):
    aggregate_unbalanced_trades()
    form = ClosedTradeFilterForm(request.GET)
    if form.is_valid():
        d = form.cleaned_data
        closed_trades = ClosedTrade.objects.all()
        if len(d['strategies']) > 0:
            closed_trades = closed_trades.filter(strategyId__in=list(d['strategies']))
        if len(d['accounts']) > 0:
            closed_trades = closed_trades.filter(account__in=list(d['accounts']))

        if d['startdate'] is not None:
            closed_trades = closed_trades.filter(exitTime__gte=d['startdate'])
        if d['enddate'] is not None:
            closed_trades = closed_trades.filter(exitTime__lte=d['enddate'])

    else:
        now = datetime.date.today()
        closed_trades = ClosedTrade.objects.all().filter(exitTime__gte=(now - datetime.timedelta(weeks=4)))
        form = ClosedTradeFilterForm()

    closed_trades = closed_trades.order_by('-exitTime')

    closed_trades_prime = closed_trades.order_by('exitTime')

    cum_profits = make_cumulative_profits(closed_trades_prime)

    template = loader.get_template('dashboard/closed_trades.html')
    context = {
            'closed_trades' : closed_trades,
            'closed_trades_filter_form' : form,
            'cumulative_profits' : cum_profits,
            'user' : request.user }
    return HttpResponse(template.render(context, request))

@transaction.atomic
def do_rebalance():
    ClosedTrade.objects.all().delete()
    Trade.objects.all().update(balanced=False)

@login_required
def rebalance_closed_trades(request):
    do_rebalance()
    return HttpResponseRedirect(reverse('closed_trades_index'))

@login_required
def performance(request):
    aggregate_unbalanced_trades()
    all_accounts = set()
    for trade in ClosedTrade.objects.all():
        if trade.account != 'demo':
            all_accounts.add(trade.account)

    closed_trades = ClosedTrade.objects.exclude(account='demo').order_by('exitTime')
    trades = Trade.objects.exclude(account='demo').order_by('timestamp')
    trades = Trade.objects.exclude(account='demo').order_by('timestamp')

    dates = []
    columns = {}
    for account in all_accounts:
        columns[account] = []
    timeframe = request.GET.get('timeframe')
    if timeframe is None:
        timeframe = 'daily'
    if timeframe == 'daily':
        prev_day = None
        for trade in closed_trades:
            if prev_day != trade.exitTime.date():
                prev_day = trade.exitTime.date()
                dates.append(prev_day)
                for account in all_accounts:
                    columns[account].append(0)
            columns[trade.account][-1] += trade.profit
    elif timeframe == 'weekly':
        epoch = datetime.date(1970, 1, 5)
        prev_week = None
        for trade in closed_trades:
            this_week = (trade.exitTime.date() - epoch).days // 7
            if prev_week != this_week:
                prev_week = this_week
                week_end = epoch + datetime.timedelta(weeks=prev_week, days=6)
                dates.append(week_end)
                for account in all_accounts:
                    columns[account].append(0)
            columns[trade.account][-1] += trade.profit
    elif timeframe == 'monthly':
        epoch = datetime.date(1970, 1, 1)
        prev_month = None
        for trade in closed_trades:
            this_month = trade.exitTime.date().month
            if prev_month != this_month:
                prev_month = this_month
                this_date = trade.exitTime.date()
                month_end = datetime.date(this_date.year, this_date.month, calendar.monthrange(this_date.year, this_date.month)[1])
                dates.append(month_end)
                for account in all_accounts:
                    columns[account].append(0)
            columns[trade.account][-1] += trade.profit

    results = { 'total' : { 'pnl' : 0, 'profit' : 0, 'loss' : 0 } }

    for account in all_accounts:
        results[account] = { 'pnl' : 0, 'profit' : 0, 'loss' : 0 }

    for trade in closed_trades:
        if trade.account != 'demo':
            results['total']['pnl'] += trade.profit
            results[trade.account]['pnl'] += trade.profit

            if trade.profit > 0:
                results['total']['profit'] += trade.profit
                results[trade.account]['profit'] += trade.profit
            else:
                results['total']['loss'] -= trade.profit
                results[trade.account]['loss'] -= trade.profit

    results['total']['pf'] = results['total']['profit'] / results['total']['loss']
    results['total']['commission'] = trades.aggregate(Sum('commission'))['commission__sum']

    template = loader.get_template('dashboard/performance.html')
    context = {
        'user' : request.user,
        'dates' : dates,
        'columns' : columns,
        'results' : results,
        'timeframe' : timeframe
    }
    return HttpResponse(template.render(context, request))
