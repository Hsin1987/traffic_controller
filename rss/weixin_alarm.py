import requests
import json
import rospy
import time, datetime
import rospy
# from account_info import corp_id, corp_secret, agent_id
# corp_id = corp_id()
# corp_secret = corp_secret()
# agent_id = agent_id()

# Setting access_token log file
file_path = '/tmp/access_token.log'


class WXAlarm:
    def __init__(self):
        self.corp_id = 'ww0692f024800a89da'
        self.corp_secret = 'cOeCoSs49lH18MqutVyFO3Jc-1ugfnnyzAGui2OC2gE'
        self.agent_id = 1000003
        self.access_token = None
        self.connection = True

    # Access token, use it when the saved token became invalid.
    def gen_access_token(self):
        get_token_url = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=%s&corpsecret=%s'\
                        % (self.corp_id, self.corp_secret)
        # print(get_token_url)
        counter = 0
        while True:
            try:
                r = requests.get(get_token_url)
                break
            except:
                counter += 1
            if counter > 3:
                rospy.logwarn("[RSS] Connection Fail. Unable to sent out info.")
                return

        request_json = r.json()
        this_access_token = request_json['access_token']
        r.close()
        # Write the token into file
        try:
            f = open(file_path, 'w+')
            f.write(this_access_token)
            f.close()
        except Exception as e:
            rospy.logerror("[RSS] Generate Token Error: "+str(e))

        # Return the access_token
        return this_access_token

    def get_access_token_from_file(self):
        try:
            f = open(file_path, 'r+')
            this_access_token = f.read()
            f.close()
            return this_access_token
        except Exception as e:
            rospy.logerror("[RSS] Get_Access_Token_from_File Error: " + str(e))

    def sent(self, message,  to_user='@all'):
        flag = True
        counter = 0
        while flag:
            try:
                send_message_url = 'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=%s' % self.access_token
                message_params = {
                    "touser": to_user,
                    "msgtype": "text",
                    "agentid": self.agent_id,
                    "text": {
                        "content": message
                    },
                    "safe": 0
                }
                r = requests.post(send_message_url, data=json.dumps(message_params))
                # print('post success %s ' % r.text)
                rospy.loginfo("[RSS] post success.")
                # Determine whether sending is successful or not. If not, execute exception function.
                request_json = r.json()
                errmsg = request_json['errmsg']
                if errmsg != 'ok':
                    raise
                # If it's successful , change the flag.
                flag = False
            except Exception as e:
                # print(e)
                rospy.logwarn('[RSS] Connection Error. Try:' + str(counter+1))
                self.access_token = self.gen_access_token()
                counter += 1

            if counter >= 3:
                rospy.logwarn('[RSS] Connection Error. Stop Trying.')
                return

    def sent_msg(self, rss_on, robot_id,  msg):
        ts = time.time()
        st = datetime.datetime.fromtimestamp(ts).strftime('%H:%M')
        if rss_on:
            self.sent(str(st) + " " + robot_id + " " + msg + " Request RSS.")


