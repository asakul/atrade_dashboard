
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib import messages

from .models import RobotInstance
import redis
import json
import datetime

def overview(request):
    r = redis.StrictRedis(unix_socket_path='/var/run/redis/redis')
    robot_instances = RobotInstance.objects.order_by('instanceId')
    robot_states = []
    index = 0
    for robot in robot_instances:
        raw_state = r.get(robot.instanceId)
        if raw_state is not None:
            state = json.loads(str(raw_state, 'utf-8'))
            try:
                positions = state['positions']
                del state['positions']
            except KeyError:
                positions = dict()
        else:
            state = dict()

        last_store = r.get(robot.instanceId + ":last_store")
        if last_store is not None:
            last_store = datetime.datetime.utcfromtimestamp(float(str(last_store, 'utf-8')[:-1]))
        index += 1
        robot_states.append((index, robot.instanceId, json.dumps(state, sort_keys=True, indent=2, separators=(',', ': ')), positions, last_store))

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

