
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib import messages

from .models import RobotInstance
import redis
import json

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
            except KeyError:
                positions = dict()
            del state['positions']
        else:
            state = dict()
        index += 1
        robot_states.append((index, robot.instanceId, json.dumps(state, sort_keys=True, indent=2, separators=(',', ': ')), positions))

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

