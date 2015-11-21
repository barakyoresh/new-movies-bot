import requests
import json
import urllib
import datetime
import time
import bot_framework
import unicodedata
import threading

import xml.etree.ElementTree as ET
from dateutil.relativedelta import relativedelta

bot = None
strike_search_url = "https://getstrike.net/api/v2/torrents/search/?phrase="
CONFIG_FILE = 'config.xml'
timeout_for_params = 5
telegram_token = None

auth_telegram_users = set()
search_rules = set()
admin_user_id = None
search_interval_seconds = 10;


'''
#example usage
response = requests.get('http://127.0.0.1:8080/query/torrents')
if not response.ok:
    response.raise_for_status()

for torrent in json.loads(response.content):
    if torrent['progress'] >= 0:
        print torrent['name']
'''

def strip_accents(s):
   return ''.join(c for c in unicodedata.normalize('NFD', s)
                  if unicodedata.category(c) != 'Mn')


def get_days_ago(date_string):
    print date_string
    if " " in date_string:
        parsed = time.strptime(date_string, '%b %d, %Y')
    else:
        return None

    dt = datetime.datetime.fromtimestamp(time.mktime(parsed))
    return (datetime.datetime.now() - dt).days


def parse_config_file():
    global search_rules, telegram_token, admin_user_id, auth_telegram_users
    tree = ET.parse(CONFIG_FILE)

    #rules
    for rule in tree.find('search_rules').iter('rule'):
        search_rules.add(rule.text)

    #telegram data
    telegram_token = tree.find('telegram_token').text
    for user_id in tree.iter('telegram_user_id'):
        auth_telegram_users.add(user_id.text)
    admin_user_id = tree.find('admin').find('telegram_user_id').text

    print 'admin user:', admin_user_id , 'rules:', search_rules, 'auth users:', auth_telegram_users

def add_search_rule_to_config_file(rule):
    if rule not in search_rules:
        tree = ET.parse(CONFIG_FILE)
        root = tree.getroot()
        new_rule = ET.SubElement(root.find('search_rules'), 'rule')
        new_rule.text = rule
        tree.write(CONFIG_FILE)

def remove_search_rule_from_config_file(rule):
    if rule in search_rules:
       tree = ET.parse(CONFIG_FILE)
       rules = tree.getroot().find('search_rules')
       for rule_to_remove in rules.iter('rule'):
           if rule_to_remove.text == rule:
               rules.remove(rule_to_remove)
               break
       tree.write(CONFIG_FILE)
       return True
    return False

def search_torrent(search_term, num_of_results):
    print search_term
    term = urllib.quote(search_term)
    response = requests.get(strike_search_url + term)

    if not response:
        return None
    if 'torrents' not in json.loads(response.content):
        return None
    return json.loads(response.content)['torrents'][:num_of_results]


def authenticate_user(message):
    if str(message.chat.id) in auth_telegram_users:
        return True
    else:
        bot.send_message(message.chat_id, ("Unauthorized user %s %s, user id: %s. Please edit bot configuration file using an authenticated account to change this." % (message.chat.first_name,
                                          message.chat.last_name, message.chat.id)))
        return False

def cmd_add_search_rule(message, params_text):
    #authenticate user
    if not authenticate_user(message):
        return

    #check if params are legal
    if not params_text:
        bot.send_message(message.chat_id, "Please enter search term")
        param_msg, params = bot.wait_for_message(message.chat_id, timeout_for_params)
        if not params:
            bot.send_message(message.chat_id, "No search parameters received - aborting operation")
            return
    else:
        params = params_text

    add_search_rule_to_config_file(params_text)
    parse_config_file()

    bot.send_message(message.chat_id, 'Term \'' + params_text + '\' successfully added.')

def cmd_remove_search_rule(message, params_text):
    #authenticate user
    if not authenticate_user(message):
        return

    #check if params are legal
    if not params_text:
        bot.send_message(message.chat_id, "Please enter search term to remove")
        param_msg, params = bot.wait_for_message(message.chat_id, timeout_for_params)
        if not params:
            bot.send_message(message.chat_id, "No search parameters received - aborting operation")
            return
    else:
        params = params_text

    removed = remove_search_rule_from_config_file(params)

    if removed:
        parse_config_file()
        bot.send_message(message.chat_id, 'Term \'' + params + '\' successfully removed.')
    else:
        bot.send_message(message.chat_id, 'Term \'' + params + '\' removal failed.')



def active_rules_string():
    active_rules_str = "Currently active search rules:"
    for rule in search_rules:
        active_rules_str += "\n" + rule
    return active_rules_str

def cmd_active_rules(message, param_text):
    bot.send_message(message.chat_id, active_rules_string())


def threading_auto_search():
    for rule in search_rules:
        print search_torrent(rule, 8)

    threading.Timer(search_interval_seconds, threading_auto_search).start()


def main():
    global bot
    #parse config file
    parse_config_file()

    # setup bot commands
    bot = bot_framework.Bot(token = telegram_token)
    bot.add_command(cmd_name='/rules', cmd_cb=cmd_active_rules, cmd_description='Show a list of current active search terms.')
    bot.add_command(cmd_name='/newrule', cmd_cb=cmd_add_search_rule, cmd_description='Add new search rule to be automatically searched, use "/newrule <term>" to add rule directly')
    bot.add_command(cmd_name='/removerule', cmd_cb=cmd_remove_search_rule, cmd_description='Removes a search rule from automatically searched rules, use "/removerule <term>" to remove rule directly')

    #activate bot
    #bot.activate()

    #activate auto search
    threading_auto_search()



if __name__ == "__main__":
    main()
