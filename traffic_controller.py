#!/usr/bin/python
# coding=utf-8
# from __future__ import print_function
from rss.weixin_alarm import WXAlarm
from MQTT.mqtt_template import MQTT_OBJ
from MQTT.global_logger import logger
import collections
from collections import OrderedDict
import json
import requests
import time
import datetime
import sys
import threading
import sqlite3
import atexit
# Status Locker
lock = threading.Lock()

robocall_ip = '192.168.30.132'
elevator_server_ip = '192.168.30.132'
autodoor_server_ip = '192.168.30.132'
robots_list = ['001', '002']
robot_mqtt_agent = {}
mqtt_agent = None

reboot_time = 3

# Hotel Node Setting
nodes_info = [['Station_001', 'Station_out_001', 'Station_002', 'Station_out_002',
               'Lobby', 'LuggageDock_out', 'LuggageDock', 'EVin'],
              ['101', '116', 'EVW1', 'EVW1S'],
              ['201', '216', 'EVW2', 'EVW2S'],
              ['301', '316', 'EVW3', 'EVW3S'],
              ['401', '416', 'EVW4', 'EVW4S'],
              ['501', '516', 'EVW5', 'EVW5S'],
              ['601', '616', 'EVW6', 'EVW6S'],
              ['701', '716', 'EVW7', 'EVW7S'],
              ['801', '816', 'EVW8', 'EVW8S'],
              ['901', '916', 'EVW9', 'EVW9S'],
              ['1001', '1016', 'EVW10', 'EVW10S'],
              ['1101', '1116', 'EVW11', 'EVW11S'],
              ['1201', '1216', 'EVW12', 'EVW12S'],
              ['1301', '1316', 'EVW13', 'EVW13S']]
# Quick Searching Floor Node
floor_node_dict = OrderedDict()

"""Booking System"""
# Robot online booking dict.
robots_registration = OrderedDict()
# Robot Last position booking dict.
robots_position = OrderedDict()
# Robot online booking dict.
robots_status = OrderedDict()
# Robot Current Path booking dict.
robots_path_record = OrderedDict()
# Node registration booking dict.
nodes_registration = OrderedDict()

# RSS
rss_on = True
rss_notification = WXAlarm()

# Database
sqlite_file = '/home/ubuntu/amr_status_db.sqlite'


def reboot_agent():
    msg = "[TC][reboot_agent] Trigger Daily Reboot of the service system."
    logger.info(msg)
    reboot_elevator(elevator_server_ip)
    reboot_autodoor(autodoor_server_ip)


def reboot_elevator(ev_ip):
    retry = 10
    payload = {'pw': 'elevator_server'}

    uri = 'http://' + ev_ip + ':8080/reboot'
    for counter in range(retry):
        try:
            req = requests.get(uri, params=payload, timeout=3)
            if req.ok:
                logger.info('[TC][EV_Agent] Reboot EV.')
                return True
            else:
                time.sleep(1.0)
        except requests.exceptions.Timeout:
            logger.info('[TC][EV_Agent] request timeout: ' + str(counter) + '/' + str(retry))
            pass
        except requests.exceptions.RequestException as e:
            # catastrophic error. bail.
            logger.info('[TC][EV_Agent] request exceptions: ' + str(e))

    return False


def reboot_autodoor(ip):
    retry = 10
    payload = {'pw': '@Advrobot'}

    uri = 'http://' + ip + ':8080/reboot'
    for counter in range(retry):
        try:
            req = requests.get(uri, params=payload, timeout=3)
            if req.ok:
                logger.info('[TC][Autodoor_Agent] Reboot EV.')
                return True
            else:
                time.sleep(1.0)
        except requests.exceptions.Timeout:
            logger.info('[TC][Autodoor_Agent] request timeout: ' + str(counter) + '/' + str(retry))
            pass
        except requests.exceptions.RequestException as e:
            # catastrophic error. bail.
            logger.info('[TC][Autodoor_Agent] request exceptions: ' + str(e))

    return False


def exit_handler():
    c.close()
    conn.close()
    msg = "[Traffic Controller] Application is Ending."
    mqtt_agent.client_disconnect()
    logger.info(msg)


def convert(data):
    if isinstance(data, basestring):
        return str(data)
    elif isinstance(data, collections.Mapping):
        return dict(map(convert, data.iteritems()))
    elif isinstance(data, collections.Iterable):
        return type(data)(map(convert, data))
    else:
        return data


def offline_clean_process(robot_id):
    global robots_path_record, lock
    lock.acquire()
    release_nodes = []
    if robots_path_record[robot_id] is not None:
        for node in robots_path_record[robot_id]:
            if nodes_registration[node] == robot_id:
                nodes_registration[node] = None
                release_nodes.append(node)
        try:
            release_nodes.remove(robots_position[robot_id])
            nodes_registration[robots_position[robot_id]] = robot_id
        except:
            pass

        msg = "[TC][Offline_Clean_Process] clean " + str(robot_id) + " booking path: " + str(release_nodes)
        logger.info(msg)
        rss_notification.sent_msg(rss_on, 'FU-' + robot_id, str(msg))

    if robots_position[robot_id] is not None:
        msg = "[TC][Offline_Clean_Process] " + str(robot_id) + " last position: " + str(robots_position[robot_id])
        logger.info(msg)
        rss_notification.sent_msg(rss_on, 'FU-' + robot_id, str(msg))

    else:
        msg = "[TC][Offline_Clean_Process] " + str(robot_id) + " last position is None."
        logger.info(msg)
        rss_notification.sent_msg(rss_on, 'FU-' + robot_id, str(msg))


def offline_check_process(robot_id):
    record = []
    for i in range(10):
        if robots_registration[robot_id] == 'offline':
            record.append(0)
        else:
            record.append(1)
        time.sleep(1.0)

    score = sum(record) / len(record)
    if score >= 0.1:
        logger.info(
            "[Offline_Check_Process] " + str(robot_id) + " confirms online.")
    else:
        logger.info(
            "[Offline_Check_Process] " + str(robot_id) + " confirms offline.")
        offline_clean_process(robot_id)


def robot_monitor_001(client, userdata, message):
    global robots_registration
    logger.info(
        "[robot_monitor_001] 001/available:  " + str(message.payload) + "(Q" + str(message.qos) + ", R" + str(
            message.retain) + ")")
    current = message.payload
    last = robots_registration['001']
    robots_registration['001'] = current
    if last == 'online' and current == 'offline':
        check_thread = threading.Thread(target=offline_check_process, args=('001',))
        check_thread.daemon = True
        check_thread.start()


def robot_monitor_002(client, userdata, message):
    global robots_registration
    logger.info(
        "[robot_monitor_002] 002/available:  " + str(message.payload) + "(Q" + str(message.qos) + ", R" + str(
            message.retain) + ")")
    current = message.payload
    last = robots_registration['002']
    robots_registration['002'] = message.payload
    if last == 'online' and current == 'offline':
        check_thread = threading.Thread(target=offline_check_process, args=('002',))
        check_thread.daemon = True
        check_thread.start()


def robot_position_agent(robot_id, robot_position):
    global nodes_registration, lock, robots_path_record
    lock.acquire()

    # Loading the task path of the robot
    robot_current_path = robots_path_record[robot_id]

    # Registered in robots_position bookkeeping.
    robots_position[robot_id] = robot_position

    if robot_current_path is not None:
        if robot_position in robot_current_path:
            for i, node in enumerate(robot_current_path):
                if i != 0 and robot_position == node:
                    release_node = robot_current_path[i-1]
                    # Clear the Last Node
                    nodes_registration[release_node] = None
                    logger.info(
                        "[robot_position_agent] release  " + str(release_node) + " node.")
                    # Check other robot's path.
                    for robot in robots_list:
                        if robot != robot_id:
                            # Check the path.
                            if robots_path_record[robot] is not None:
                                if release_node in robots_path_record[robot]:
                                    lock.release()
                                    path_agent(robot, robots_path_record[robot])
                                    return

                else:
                    pass
        else:
            pass
    lock.release()


def nodes_registration_init(info):
    global floor_node_dict
    nodes_dict = OrderedDict()

    # Init Floor Node dict
    for floor, floor_nodes in enumerate(info):
        if floor == 0:
            floor_node_dict['1'] = []
            for node in floor_nodes:
                floor_node_dict['1'].append(node)
        elif floor == 1:
            for node in floor_nodes:
                floor_node_dict['1'].append(node)
        else:
            floor_node_dict[str(floor)] = []
            for node in floor_nodes:
                floor_node_dict[str(floor)].append(node)

    # Build up all the nodes
    for i, nodes_list in enumerate(info):
        if nodes_list[0].isdigit() and nodes_list[1].isdigit():
            room_list = []
            for j in range(int(nodes_list[0]), int(nodes_list[1])+1):
                room_list.append(str(j))
            info[i] = nodes_list[2:] + room_list

    # Build up the nodes registration dictionary.
    for i, nodes_list in enumerate(info):
        nodes_temp = nodes_list[:]
        for node in nodes_temp:
            nodes_dict[node] = None
    return nodes_dict


def path_manager(client, userdata, message):
    global nodes_registration, robots_path_record, lock
    logger.info(
        "[path_manager] :  " + str(message.payload) + "(Q" + str(message.qos) + ", R" + str(
            message.retain) + ")")
    temp = convert(json.loads(message.payload))
    robot_id = str(temp['robot_id'])
    req_path = temp['path']

    # Add robot_id for station.
    for i, node in enumerate(req_path):
        if node.startswith('Station'):
            req_path[i] = req_path[i] + '_' + robot_id
    robots_path_record[robot_id] = req_path
    path_agent(robot_id, req_path)


def path_agent(robot_id, req_path):
    lock.acquire()
    allow_path = []
    for i, node in enumerate(req_path):
        if nodes_registration[node] is None or nodes_registration[node] == robot_id:
            # Prohibit Robot in the same Floor
            if node.startswith('EVW'):
                floor = node[3:]
                floor_nodes = floor_node_dict[floor]
                for check_node in floor_nodes:
                    if nodes_registration[check_node] != robot_id:
                        if nodes_registration[check_node] is not None:
                            break
                        else:
                            pass
                    else:
                        pass

            nodes_registration[node] = robot_id
            allow_path.append(node)
        else:
            break

    reply_topic = robot_id + '/task_path'
    # 001/task_path
    payload_str = json.dumps(allow_path)

    for counter in range(10):
        mqtt_result = mqtt_agent.publish_blocking(topic=reply_topic, payload=payload_str,
                                                  qos=2, retain=False, timeout=10)
        mqtt_rc = mqtt_result[1]
        if mqtt_rc is not None:
            logger.info(
                "[path_manager]: assigned path [ " + payload_str + "] to " + robot_id + ' robot.')
            lock.release()
            return
        else:
            time.sleep(1.0)


def amr_status_agent(client, userdata, message):
    global nodes_registration, lock, robots_status
    lock.acquire()
    amr_status_dict = convert(json.loads(message.payload))
    # Update the robots_status
    robots_status[amr_status_dict['r_id']] = amr_status_dict['status']

    if amr_status_dict['status'] == 'init':
        msg = "[TC][amr_status_agent] " + str(amr_status_dict['r_id']) + \
              " init position: " + str(amr_status_dict['position'])
        logger.info(msg)
        for node in nodes_registration.keys():
            if nodes_registration[node] == amr_status_dict['r_id']:
                nodes_registration[node] = None
                msg = "[TC][amr_status_agent] Clear " + str(amr_status_dict['r_id']) + \
                      " legacy position: " + str(nodes_registration[node])
                logger.info(msg)
        nodes_registration[amr_status_dict['position']] = amr_status_dict['r_id']
        lock.release()
    elif amr_status_dict['status'] == 'shutdown':
        robots_registration[amr_status_dict['r_id']] = 'shutdown'
        # FOR TEST
        print(robots_registration)
        node_list = []
        for node in nodes_registration.keys():
            if nodes_registration[node] == amr_status_dict['r_id']:
                node_list.append(node)
                nodes_registration[node] = None
        msg = "[TC][amr_status_agent] " + str(amr_status_dict['r_id']) + \
              " Shutdown Process, Clear legacy position: " + str(node_list)
        logger.info(msg)
        lock.release()
    else:
        lock.release()
        # robot_id, robot_position
        robot_position_agent(amr_status_dict['r_id'], amr_status_dict['position'])

    # SQLite Logging Section
    ts = time.time()
    now = datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')
    item = (now, amr_status_dict['ts_start'], amr_status_dict['status'],
            amr_status_dict['mission'], amr_status_dict['position'], amr_status_dict['closet_position'],
            amr_status_dict['capacity'],
            amr_status_dict['EV_abort'], amr_status_dict['EV_entering_abort'], amr_status_dict['mb_abort'],
            amr_status_dict['mb_abort_counter'])

    table = 'amr_'+amr_status_dict['r_id']+'_status_db'
    cmd = 'insert into ' + table + ' values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
    # Connecting to the database file
    conn_2 = sqlite3.connect(sqlite_file)
    c2 = conn_2.cursor()
    c2.execute(cmd, item)
    conn_2.commit()
    c2.close()
    conn_2.close()
    return


def traffic_controller():
    global robots_registration, nodes_registration, mqtt_agent, robot_mqtt_agent, robots_position
    client_name = 'traffic_controller'

    robot_mqtt_agent = {
        '001': robot_monitor_001,
        '002': robot_monitor_002
    }

    mqtt_agent = MQTT_OBJ(client_id=client_name, broker_ip=robocall_ip,
                          port=1883, keepalive=10, clean_session=False, logger=logger)

    # Init: Monitor the robots online report
    for robot_id in robots_list:
        # Init the status
        robots_path_record[robot_id] = None
        robots_position[robot_id] = None
        robots_registration[robot_id] = 'offline'
        robots_status[robot_id] = None

        # sub MQTT Online Topic
        robot_available_topic = robot_id + "/available"
        mqtt_agent.add_subscriber([(robot_available_topic, 2, robot_mqtt_agent[robot_id])])

    # TODO: ADD EV, Autodoor online monitor
    """
    # EV online monitor
    robot_position_report_channel = "ev_server/available"
    mqtt_agent.add_subscriber([(robot_position_report_channel, 2, robot_position_agent)])
    """

    # Init the Nodes Registration
    # AMR Report Channel
    amr_status_agent_channel = "amr_status_agent"
    mqtt_agent.add_subscriber([(amr_status_agent_channel, 2, amr_status_agent)])

    nodes_registration = nodes_registration_init(nodes_info)
    mqtt_agent.add_subscriber([('req_path', 2, path_manager)])

    # AMR Report Channel
    # robot_position_report_channel = "amr_position"
    # mqtt_agent.add_subscriber([(robot_position_report_channel, 2, robot_position_agent)])

    # Keep it Spinning.
    while True:
        if time.localtime().tm_hour == reboot_time and time.localtime().tm_min == 0:
            while True:
                available_check = 0
                print(robots_status)
                for robot_id in robots_list:
                    # Init the status
                    if robots_status[robot_id] == "available":
                        available_check += 1

                if available_check == len(robots_list):
                    lock.acquire()
                    logger.info('[TC] Start Daily Reboot.')
                    reboot_agent()
                else:
                    time.sleep(10)
        else:
            time.sleep(10)
            print(nodes_registration)
            pass


if __name__ == '__main__':
    try:
        # Open SQLite
        # Connecting to the database file
        conn = sqlite3.connect(sqlite_file)
        c = conn.cursor()

        # Creating a new SQLite table
        c.executescript("""CREATE TABLE IF NOT EXISTS amr_001_status_db(tid REAL, ts_start REAL, amr_status TEXT,
                             mission TEXT, task_position TEXT, closet_position TEXT,
                             capacity REAL,
                             EV_abort INTEGER, EV_entering_abort INTEGER, mb_abort INTEGER,
                             mb_abort_counter INTEGER);""")

        # Creating a new SQLite table
        c.executescript("""CREATE TABLE IF NOT EXISTS amr_002_status_db(tid REAL, ts_start REAL, amr_status TEXT,
                                     mission TEXT, task_position TEXT, closet_position TEXT,
                                     capacity REAL,
                                     EV_abort INTEGER, EV_entering_abort INTEGER, mb_abort INTEGER,
                                     mb_abort_counter INTEGER);""")

        # c.close()
        # conn.close()
        atexit.register(exit_handler)
        traffic_controller()
    except KeyboardInterrupt:
        print >> sys.stderr, '\nExiting by user request.\n'
        sys.exit(0)

