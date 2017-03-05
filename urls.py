
from django.conf.urls import url

from . import views

urlpatterns = [
        url(r'^$', views.overview, name='overview'),
        url(r'^add_instance$', views.add_instance, name='add_instance'),
        url(r'^delete_instance/(?P<instance_id>[^/]+)$', views.delete_instance, name='delete_instance'),

]
