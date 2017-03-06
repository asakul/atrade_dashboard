
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib import messages

from .models import RobotInstance, Trade
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
    trades = Trade.objects.all()
    template = loader.get_template('dashboard/trades.html')
    context = {
            'trades' : trades
            }
    return HttpResponse(template.render(context, request))
