import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "atrade_dashboard.settings")
import django
django.setup()

import zmq
import argparse
import datetime
from dashboard.models import Trade

def parse_timestamp(ts):
    return datetime.datetime.strptime(ts, '%Y-%m-%d %H:%M:%S.%f')

def store_trade(j):
    quantity = int(j['quantity'])
    if j['operation'] == 'sell':
        quantity = -quantity
    elif j['operation'] != 'buy':
        raise Exception('Invalid operation: ' + j['operation'])

    try:
        comment = j['order-comment']
    except KeyError:
        comment = ""

    try:
        commission = float(j['commission'])
    except KeyError:
        commission = ""
    ts = parse_timestamp(j['execution-time'])
    trade = Trade(account=j['account'], security=j['security'], price=float(j['price']), quantity=quantity, volume=float(j['volume']), volumeCurrency=j['volume-currency'], strategyId=j['strategy'],
                signalId=j['signal-id'], comment=comment, timestamp=ts, commission=commission)
    trade.save()


def handle_cmd(cmd):
    try:
        if 'command' in cmd.keys():
            return { 'response' : 'ok' }
        elif 'trade' in cmd.keys():
            store_trade(cmd['trade'])
            return { 'response' : 'ok' }
    except Exception as e:
        print(e)
    return { 'response' : 'error' }

def main():
    parser = argparse.ArgumentParser(description='Trade sink process')
    parser.add_argument('-e', '--endpoint', action='store', help='Trade sink endpoint')
    args = parser.parse_args()

    ctx = zmq.Context.instance()
    s = ctx.socket(zmq.REP)
    s.bind(args.endpoint)

    while True:
        events = s.poll(1000, zmq.POLLIN)
        if events == zmq.POLLIN:
            cmd = s.recv_json()
            response = handle_cmd(cmd)
            s.send_json(response)


if __name__ == "__main__":
    main()
