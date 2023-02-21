#!/usr/bin/env python3

import sqlite3
import socket
import time
import re
import json
import os
import requests
import xmltodict
import epics
import threading
import logging

from flask import Flask
from flask import request as flask_request
from flask import render_template

class globals:
	db = None

	lock = None

	lighthouses = ['acq1001_074']

	lighthouse = None

	tty_servers = []

	active_ttys = {}

	claims = {}

	web_port = 5000

	update_rate = 1

	active_uuts = set()

	table_name = 'states'

	primary_key = 'uut_name'

	table_schema = {
		'delay'		: 'INTEGER',
		'uut_name' 	: 'TEXT PRIMARY KEY',
		'tty'		: 'TEXT',
		'user'		: 'TEXT',
		'test'		: 'TEXT',
		'uptime'	: 'INTEGER',
		'cstate'	: 'INTEGER',
		'tstate'	: 'INTEGER',
		'shot'		: 'INTEGER',
		'clk_set'	: 'REAL',
		'clk_freq'	: 'REAL',
		'firmware'	: 'TEXT',
		'fpga'		: 'TEXT',
		'temp'		: 'REAL',
		'conn_type'	: 'TEXT',
		'ip'		: 'TEXT',
	}
	mapped_knobs = {
		'host'					: 'uut_name',
		'SYS:UPTIME'			: 'uptime',
		'SYS:0:TEMP'			: 'temp',
		'SYS:VERSION:SW'		: 'firmware',
		'SYS:VERSION:FPGA'		: 'fpga',
		'MODE:CONTINUOUS:STATE' : 'cstate',
		'MODE:TRANS_ACT:STATE' 	: 'tstate',
		'1:SHOT'				: 'shot',
		'0:SIG:CLK_MB:SET'		: 'clk_set',
		'0:SIG:CLK_MB:FREQ'		: 'clk_freq',
		'USER'					: 'user',
		'TEST_DESCR'			: 'test',
	}

class Uut_connector:
	def __init__(self, hostname):
		self.hostname = hostname
		self.db = globals.db
		self.state = {}
		self.state[globals.primary_key] = hostname
		self.offline = 0
		self.last_contact = 0

		self.epic_last = 0
		self.epics_callbacks = []
		self.check_legacy()
		self.create_record()

	def check_legacy(self):
		self.url = f'http://{self.hostname}/d-tacq/data/status.xml'
		try:
			response = requests.head(self.url)
			self.state['ip'] = socket.gethostbyname(self.hostname)
		except Exception as e:
			#print(e)
			self.__connection_down()
			return
		if response.status_code != 200:
			self.legacy = True
			self.state['conn_type'] = 'EPICS'
			self.get_state = self.__get_status_epics
			return
		self.legacy = False
		self.state['conn_type'] = 'WEB'
		self.get_state = self.__get_status_http

	def __get_status_http(self):
		try:
			response = requests.get(self.url, timeout=2.50)
		except Exception as e:
			#print(e)
			self.__connection_down()
			return
		if response.status_code != 200:
			self.__connection_down()
			return
		data = xmltodict.parse(response.content)
		self.state.update(self.__data_extractor(data))
		self.__connection_up()

	def __data_extractor(self, data):
		extracted_data = {}
		if type(data) is not list:
			if '@n' in data:
				if data['@n'] in globals.mapped_knobs:
					extracted_data[globals.mapped_knobs[data['@n']]] = data['v']
				return extracted_data
			for key, value in data.items():
				if type(value) is not str:
					extracted_data.update(self.__data_extractor(value))
					continue
				if key in globals.mapped_knobs:
					extracted_data[globals.mapped_knobs[key]] = value
			return extracted_data
		if type(data) is list:
			for item in data:
				extracted_data.update(self.__data_extractor(item))
		return extracted_data

	def __get_status_epics(self):
		if not self.epic_last:
			if self.is_epics_down():
				self.kill_self()
			#prCyan(f'getting epics {self.hostname}')
			knobs = globals.mapped_knobs.copy()
			del knobs['host']
			for knob in knobs:
				knob = f'{self.hostname}:{knob}'
				self.epics_callbacks.append(epics.PV(knob, auto_monitor=True, form='native', callback=self.__epics_callback))
			self.epic_last = time.time()
			return
		if time.time() - self.epic_last > 60:
			for callback in self.epics_callbacks:
				callback.disconnect()
			self.epic_last = 0
			self.epics_callbacks = []
		self.offline += 1


	def __epics_callback(self, **kws):
		host = f'{self.hostname}:'
		key = kws['pvname'].replace(host,'')
		value = kws['value']
		self.state[globals.mapped_knobs[key]] = value
		self.offline = 0

	def check_tty(self):
		if self.hostname in globals.active_ttys:
			self.state['tty'] = globals.active_ttys[self.hostname]

	def create_record(self):
		keys = ''
		values = ''
		for key, value in self.state.items():
			keys += f'{key},'
			values += f'"{value}",'
		sql = f'INSERT OR IGNORE INTO {globals.table_name} ({keys[:-1]}) VALUES ({values[:-1]})'
		self.__run_query(sql)

	def update_record(self):
		#print(self.state)
		self.state['delay'] = int(self.offline)
		if self.hostname in globals.claims:
			self.state['user'] = globals.claims[self.hostname]['user']
			self.state['test'] = globals.claims[self.hostname]['test']
		changes = ''
		for key, value in self.state.items():
			if key == globals.primary_key:
				continue
			changes += f'{key} = "{value}",'
		sql = f'UPDATE {globals.table_name} SET {changes[:-1]} where {globals.primary_key} = "{self.state[globals.primary_key]}"'
		self.__run_query(sql)

	def delete_record(self):
		sql = f'DELETE FROM {globals.table_name} WHERE {globals.primary_key} = "{self.state[globals.primary_key]}"'
		self.__run_query(sql)

	def __run_query(self, sql):
		cursor = self.db.cursor()
		try:
			cursor.execute(sql)
		except Exception as e:
			#print(e)
			self.__connection_down()

	def __connection_down(self):
		prRed(f"{self.hostname} is DOWN")
		if not self.offline:
			self.last_contact = time.time()
		self.offline = time.time() - self.last_contact

	def __connection_up(self):
			self.offline = 0
			self.last_contact = 0

	def is_epics_down(self):
		try:
			s = socket.socket()
			s.settimeout(3)
			s.connect((self.hostname, 80))
		except Exception as e:
			#print(e)
			return True
		return False

	def is_dead(self):
		max_wait = 30
		if self.offline > max_wait:
			return True
		return False

	def kill_self(self):
		globals.active_uuts.remove(self.hostname)
		self.delete_record()
		prRed(f'{self.hostname} is offline removing')
		exit()

######################################################################################



def main():
	get_config_file()
	get_claims_db()
	create_state_db()
	find_lighthouse()
	handler = threading.Thread(target=thread_handler)
	handler.start()
	start_web()

def get_config_file():
	config_file = 'config.json'
	valid_keys = {'lighthouses','update_rate','web_port','tty_servers'}
	if os.path.exists(config_file):
		file = open(config_file, "r")
		data = json.loads(file.read())
		for key in valid_keys:
			if key in data:
				setattr(globals, key, data[key])

def get_claims_db():
		db_file = 'multimon_claims.db'
		claim_table = 'claims'
		claim_schema = {
			'uut_name' 	: 'TEXT PRIMARY KEY',
			'user'		: 'TEXT',
			'test'		: 'TEXT',
		}
		db = sqlite3.connect(db_file)
		db.row_factory = sqlite3.Row
		cursor = db.cursor()
		if not table_exists(cursor, claim_table):
			prYellow("Creating claims db")
			sql = build_create_sql(claim_table, claim_schema)
			cursor.execute(sql)
		claims = cursor.execute(f"SELECT * FROM {claim_table}").fetchall()
		for claim in claims:
			globals.claims[claim['uut_name']] = {'user': claim['user'],'test': claim['test']}
		db.close()

def create_state_db():
	db = sqlite3.connect(":memory:", check_same_thread=False)
	cursor = db.cursor()
	if not table_exists(cursor, globals.table_name):
		sql = build_create_sql(globals.table_name, globals.table_schema)
		cursor.execute(sql)
	globals.db = db

def build_create_sql(table_name, table_schema):
	sql = f"CREATE TABLE {table_name} ("
	for column in table_schema.items():
		sql += f"{column[0]} {column[1]},"
	sql = sql[:-1] + ")"
	return sql

def table_exists(cursor, table_name):
	sql = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
	tables = cursor.execute(sql).fetchall()
	if len(tables) == 0:
		return False
	return True

def find_lighthouse():
	for uut in globals.lighthouses:
		if check_if_casw(uut):
			prBlue(f"casw server established {uut}")
			globals.lighthouse = uut
			return
	exit(prRed("No Valid casw systems found"))

def check_if_casw(host):
	s = socket.socket()
	s.settimeout(3)
	try:
		s.connect((host, 54555))
		data = s.recv(1024)
	except:
		return False
	else:
		if not data:
			return False
		s.close()
		return True

def thread_handler():
	tty_monitor = threading.Thread(target=get_tty_connections)
	tty_monitor.start()
	whitelist = ['z7io_011','acq2106_350']
	whitelist = []
	s = connect_to_lighthouse()
	expr = re.compile('([\w]+)[\.\w\-]*:5064')
	uut_threads = {}
	last_dead_check = time.time()
	while True:
		#prCyan(f'Thread handler id {threading.get_ident()}')
		matches = get_lighthouse_data(s)
		if not matches:
			s = connect_to_lighthouse()
			continue
		for hostname in matches:
			if whitelist:
				if hostname not in whitelist:
					continue
			if hostname in globals.active_uuts:
				continue
			if hostname.isnumeric():
				continue
			prGreen(f'Adding {hostname}')
			globals.active_uuts.add(hostname)
			uut_object = Uut_connector(hostname)
			clip_thread = threading.Thread(target=clipper, args=(uut_object,))
			clip_thread.start()
			uut_threads[hostname] = clip_thread
		#prYellow(f'{len(globals.active_uuts)} uuts active')
		time.sleep(1)
		if time.time() - last_dead_check > 60:
			prRed('Checking dead threads')
			last_dead_check = time.time()
			for hostname in uut_threads.copy().keys():
				if not uut_threads[hostname].is_alive():
					if hostname in globals.active_uuts:
						globals.active_uuts.remove(hostname)
					del uut_threads[hostname]
					prRed(f'{hostname} thread has died unexpectedly')

def connect_to_lighthouse():
	s = socket.socket()
	try:
		s.connect((globals.lighthouse, 54555))
	except:
		find_lighthouse()
		s.connect((globals.lighthouse, 54555))
	return s

def get_lighthouse_data(socket):
	expr = re.compile('([\w]+)[\.\w\-]*:5064')
	data = socket.recv(1024).decode().strip()
	matches = expr.findall(data)
	return matches

def get_tty_connections():
	while True:
		for tty in globals.tty_servers:
			url = f'http://{tty}/cgi-bin/showconsoles.cgi'
			try:
				headers = {'Accept-Encoding': 'identity'}
				response = requests.get(url, headers=headers)
			except Exception as e:
				continue
			if response.status_code != 200:
				continue
			for line in response.content.decode().split('\n'):
				match = re.match('tty_([a-zA-Z0-9_]+)', line)
				if match:
					hostname = match[1]
					globals.active_ttys[hostname] = tty
		time.sleep(60)

def clipper(uut_object):
	while True:
		uut_object.get_state()
		uut_object.check_tty()
		uut_object.update_record()
		time.sleep(globals.update_rate)
		if uut_object.is_dead():
			uut_object.kill_self()


def start_web():
	app = Flask(__name__, template_folder='.')
	from werkzeug.middleware.proxy_fix import ProxyFix
	app.wsgi_app = ProxyFix(app.wsgi_app, x_host=1)

	@app.route("/")
	def index():
		return render_template('index.html')

	@app.route("/state.json")
	def get_state():
		sql = f"SELECT * FROM {globals.table_name} ORDER BY {globals.primary_key};"
		return json.dumps(sql_to_dict(sql))
	def sql_to_dict(sql):
		try:
			globals.db.row_factory = sqlite3.Row
			cursor = globals.db.cursor()
			rows = cursor.execute(sql).fetchall()
			unpacked = [{k: item[k] for k in item.keys()} for item in rows]
			return unpacked
		except Exception as e:
			print(f"Failed to execute query: {sql} Error: {e}")
			return []

	@app.route("/set_claim", methods=['POST'])
	def process_data():
		try:
			data = flask_request.json
			insert_record(data)
			if not data['uut_name']:
				return 'failure', 405
			globals.claims[data['uut_name']] = {'user':data['user'],'test':data['test']}
		except:
			return 'failure', 405
		return 'success', 201
	def insert_record(data):
		keys = ''
		values = ''
		for key, value in data.items():
			keys += f'{key},'
			values += f'"{value}",'
		db = sqlite3.connect('multimon_claims.db')
		sql = f'INSERT OR REPLACE INTO claims ({keys[:-1]}) VALUES ({values[:-1]})'
		cursor = db.cursor()
		cursor.execute(sql)
		db.commit()
		db.close()

	@app.route("/hosts")
	def return_hosts():
		sql = f'SELECT "ip", "uut_name" FROM {globals.table_name} ORDER BY {globals.primary_key};'
		buffer = ""
		unpacked = sql_to_dict(sql)
		for row in unpacked:
			buffer += f"{row['uut_name']} {row['ip']}<br>"
		return buffer

	logging.getLogger('werkzeug').disabled = True
	app.run(host="0.0.0.0", port=globals.web_port)

def prRed(skk): print("\033[91m{}\033[00m" .format(skk))
def prGreen(skk): print("\033[92m{}\033[00m" .format(skk))
def prYellow(skk): print("\033[93m{}\033[00m" .format(skk))
def prPurple(skk): print("\033[95m{}\033[00m" .format(skk))
def prCyan(skk): print("\033[96m{}\033[00m" .format(skk))
def prBlue(skk): print("\033[94m{}\033[00m" .format(skk))


if __name__ == '__main__':
	main()

