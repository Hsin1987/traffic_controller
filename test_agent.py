#!/usr/bin/python
# coding=utf-8
# from __future__ import print_function

from MQTT.mqtt_template import MQTT_OBJ
from MQTT.global_logger import logger
import sys
import collections
from collections import OrderedDict
import json
import time
mqtt_agent = None
robocall_ip = '192.168.30.132'


def path_report(client, userdata, message):
    logger.info(
        "[path_report_001] 001/path:  " + str(message.payload) + "(Q" + str(message.qos) + ", R" + str(
            message.retain) + ")")


def publish_path():
    # Channel 1. MQTT
    cmd_topic = 'req_path'
    payload = {}
    payload['r_id'] = '001'
    payload['path'] = ['Station_001', 'Station_out_001', 'Lobby', 'EVW1', 'EVin', 'EVW4', '404']
    payload_str = json.dumps(payload)
    mqtt_result = mqtt_agent.publish_blocking(topic=cmd_topic, payload=payload_str, qos=2,
                                              retain=False, timeout=3.0)
    mqtt_rc = mqtt_result[1]
    print(mqtt_rc)

pubBindings = {
    '0': publish_path
}

msg = """
0. publish_path
1: moveBaseGoal   Reached
"""

if __name__ == '__main__':
    client_name = '001'
    mqtt_agent = MQTT_OBJ(client_id=client_name, broker_ip=robocall_ip,
                          port=1883, keepalive=10, clean_session=False, logger=logger)
    assign_path = client_name + '/task_path'
    mqtt_agent.add_subscriber([(assign_path, 2, path_report)])
    time.sleep(10.0)
    publish_path()
    while True:
        time.sleep(2.0)
        """
        try:
            sys.stderr.write("\x1b[2J\x1b[H")
            print msg
            key = raw_input()
            if key in pubBindings.keys():
                pubBindings[key]()
            else:
                print('Please choose the right one.')
        except:
            print 'shit happens'
        """