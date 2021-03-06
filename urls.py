
from django.conf.urls import url

from . import views

urlpatterns = [
        url(r'^$', views.overview, name='overview'),
        url(r'^login$', views.login_view, name='login'),
        url(r'^logout$', views.logout_view, name='logout'),
        url(r'^add_instance$', views.add_instance, name='add_instance'),
        url(r'^delete_instance/(?P<instance_id>[^/]+)$', views.delete_instance, name='delete_instance'),
        url(r'^trades/$', views.trades_index, name='trades_index'),
        url(r'^add_trade/$', views.add_trade, name='add_trade'),
        url(r'^delete_trade/(?P<trade_id>[^/]+)$', views.delete_trade, name='delete_trade'),
        url(r'^closed_trades/$', views.closed_trades_index, name='closed_trades_index'),
        url(r'^rebalance_closed_trades/$', views.rebalance_closed_trades, name='rebalance_closed_trades'),
        url(r'^performance/$', views.performance, name='performance')
]
