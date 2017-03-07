
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template import loader
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib import messages

from .models import RobotInstance, Trade
from .forms import NewTradeForm
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
    trades = Trade.objects.all()
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

