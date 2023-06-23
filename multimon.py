#!/usr/bin/env python3

import os
import json
import socket
import time
import re
import requests
import threading
import xmltodict
from datetime import datetime

#import pyprctl

from bottle import route, run, response, request, static_file

class globals:
	active = set()
	data = {}
	claims = {}
	pdu_claims = {}

	topography = {}
	tty_servers = []
	tty_connections = {}

	port = 5000
	lighthouses = []
	whitelist = []
	blacklist = []

	config_file = 'config.json'
	claims_file = 'claims.json'

	table_keys = [
		'delay',
		'uut_name',
		'tty',
		'location',
		'user',
		'test',
		'pdu',
		'uptime',
		'cstate',
		'tstate',
		'shot',
		'firmware',
		'fpga',
		'temp',
		'ip',
	]

	mapped_knobs = {
		'host'					: 'uut_name',
		'SYS:UPTIME'			: 'uptime',
		'SYS:0:TEMP'			: 'temp',
		'SYS:VERSION:SW'		: 'firmware',
		'SYS:VERSION:FPGA'		: 'fpga',
		'MODE:CONTINUOUS:STATE' : 'cstate',
		'MODE:TRANS_ACT:STATE' 	: 'tstate',
		'1:SHOT'				: 'shot',
		'USER'					: 'user',
		'TEST_DESCR'			: 'test',
	}

class config:
	def load():
		filename = globals.config_file
		if os.path.exists(filename):
			print(f"[config] Loading {filename}")
			with open(filename) as file:
				data = json.loads(file.read())
				for key in data:
					setattr(globals, key, data[key])
			config.trim()
			return
		prRed(f"Error: Cannot load config {filename}")
		os._exit(1)

	def trim():
		if not globals.tty_servers:
			globals.table_keys.remove('tty')
			globals.table_keys.remove('location')
			globals.table_keys.remove('pdu')

class claim_handler:

	def load():
		filename = globals.claims_file
		if os.path.exists(filename):
			with open(filename, 'r') as file:
				try:
					data = json.loads(file.read())
					print(f"[claim_handler] Added {len(data)} claims")
					globals.claims = data
				except:
					print('[claim_handler] Unable to load claims')

		claim_handler.preload()

	def save():
		filename = globals.claims_file
		with open(filename, "w") as file:
			file.write(json.dumps(globals.claims))

	def preload():
		for uut, claim in globals.claims.items():
			if 'pdu' in claim and claim['pdu']:
				thread_handler.init_row(uut)
				globals.data[uut]['uut_name'] = uut
				globals.data[uut]['pdu'] = claim['pdu']
				globals.data[uut]['user'] = claim['user']
				globals.data[uut]['test'] = claim['test']
				globals.data[uut]['delay'] = 'OFF'
				globals.data[uut]['dead_flag'] = True

	def claim(uut, user, test, pdu, pdu_num, **kwargs):
		if uut not in globals.claims:
			globals.claims[uut] = {}
		globals.claims[uut]['user'] = user
		globals.claims[uut]['test'] = test
		globals.data[uut]['user'] = user
		globals.data[uut]['test'] = test
		claim_handler.save()

		if not globals.tty_servers:
			return True, 'Updated'

		if bool(pdu) != bool(pdu_num):
			prRed('[claim_handler] Pdu claim invalid')
			return False, 'Pdu claim invalid'

		if bool(pdu):
			pdu = f"{pdu}::{pdu_num}"
			if pdu in globals.pdu_claims:
				if globals.pdu_claims[pdu] != uut:
					return False, f"{pdu} already claimed by {globals.pdu_claims[pdu]}"
				return True, 'Updated'
			claim_handler.unclaim_pdu(uut)
			claim_handler.claim_pdu(uut, pdu)
			claim_handler.save()
			return True, 'Updated'

		claim_handler.unclaim_pdu(uut)
		claim_handler.save()
		return True, 'Updated'

	def erase(uut, **kwargs):
		globals.data[uut]['user'] = None
		globals.data[uut]['test'] = None
		if globals.tty_servers:
			claim_handler.unclaim_pdu(uut)
		del globals.claims[uut]
		claim_handler.save()
		return True, 'Erased'

	def claim_pdu(uut, pdu):
		globals.pdu_claims[pdu] = uut
		globals.claims[uut]['pdu'] = pdu
		globals.data[uut]['pdu'] = pdu
		prGreen(f"[claim_handler] Claiming {pdu} for {uut}")

	def unclaim_pdu(uut):
		pdu = globals.data[uut]['pdu']
		if pdu:
			globals.data[uut]['pdu'] = None
			globals.claims[uut]['pdu'] = None
			del globals.pdu_claims[pdu]

		if uut not in globals.active:
			prRed('[claim_handler] Erasing dead uut')
			del globals.data[uut]

class casw:
	port = 54555
	lighthouse = None
	conn = None
	expr = re.compile('([az][\w]+)\.')
	def __init__(self):
		self.scan()

	def scan(self):
		if self.conn:
			self.conn.close()
			self.conn = None
		for lighthouse in globals.lighthouses:
			print('loop')
			if self.is_online(lighthouse):
				self.lighthouse = lighthouse
				print(f"[casw] {lighthouse} is lighthouse")
				return
		prRed('Error: Unable to aquire casw lighthouse')
		os._exit(1)

	def is_online(self, host):
		s = socket.socket()
		s.settimeout(10)
		try:
			s.connect((host, self.port))
			data = s.recv(1024)
		except:
			s.close()
			return False
		else:
			if not data:
				s.close()
				return False
			s.close()
			return True

	def make_socket(self):
		if not self.conn:
			tries = 0
			while tries < 3:
				tries += 1
				self.conn = socket.socket()
				try:
					self.conn.connect((self.lighthouse, 54555))
					print(f"[casw] Connected to {self.lighthouse} casw")
					return
				except Exception as e:
					print(e)
					self.scan()
			prRed('Error: Unable to aquire casw lighthouse')
			os._exit(1)

	def get(self):
		self.make_socket()
		data = self.conn.recv(4096).decode()
		matches = self.expr.findall(data)
		return matches

class tty_handler:
	def start():
		tty_thread = threading.Thread(target=tty_handler.get_connections, name='tty_handler')
		tty_thread.daemon = True
		tty_thread.start()

	def get_connections():
		#pyprctl.set_name('tty_handler')
		time.sleep(10)
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
						globals.tty_connections[hostname] = tty
						tty_handler.update(hostname, tty)
			time.sleep(60)

	def update(hostname, tty):
		if hostname in globals.data:
			if globals.data[hostname]['tty'] == tty:
				return
			globals.data[hostname]['tty'] = tty
			globals.data[hostname]['location'] = globals.topography[tty]['name']

class thread_handler:
	def start():
		thread = threading.Thread(target=thread_handler.loop, name='thread_handler')
		thread.daemon = True
		thread.start()

	def loop():
		#pyprctl.set_name('thread_handler')
		threads = {}
		tty_handler.start()
		casw_listener = casw()
		while True:
			hostnames = casw_listener.get()
			for hostname in hostnames:
				if thread_handler.is_invalid(hostname):
					continue
				globals.active.add(hostname)
				threads[hostname] = thread_handler.new_thread(hostname)
			time.sleep(1)

	def is_invalid(hostname):
		if globals.whitelist:
			if hostname not in globals.whitelist:
				return True
		if hostname in globals.blacklist:
			return True
		if hostname in globals.active:
			return True
		return False

	def new_thread(hostname):
		print(f"[thread_handler] New uut {hostname}")
		thread = threading.Thread(target=uut_handler,name=hostname, args=(hostname,))
		thread.name = hostname
		thread.daemon = True
		thread.start()
		return thread

	def init_row(hostname):
		globals.data[hostname] = {}
		for key in globals.table_keys:
			globals.data[hostname][key] = None

class uut_connector:
	hostname = None
	ip = None
	online = True
	last_contact = 0

	def __init__(self, hostname):
		self.hostname = hostname
		self.url = f'http://{self.hostname}/d-tacq/data/status.xml'
		if self.is_invalid():
			self.online = False
			return
		self.preload()

	def is_invalid(self):
		try:
			self.ip = socket.gethostbyname(self.hostname)
		except:
			return True
		return False

	def preload(self):
		thread_handler.init_row(self.hostname)
		self.data = globals.data[self.hostname]

		self.data['uut_name'] = self.hostname
		self.data['ip'] = self.ip

		if self.hostname in globals.claims:
			self.claim = globals.claims[self.hostname]
			self.data['user'] = self.claim['user']
			self.data['test'] = self.claim['test']
			if 'pdu' in self.claim:
				if self.claim['pdu']:
					globals.data[self.hostname]['pdu'] = f"{self.claim['pdu']}"
					globals.pdu_claims[self.claim['pdu']] = self.hostname

	def update_state(self):
		try:
			response = requests.get(self.url, timeout=1)
		except:
			self.connection_down()
			return
		self.connection_up()
		if response.status_code != 200:
			return
		data = xmltodict.parse(response.content)
		globals.data[self.hostname].update(self.__data_extractor(data))

	def __data_extractor(self, data):
		#recursively gets key, values from xml
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

	def connection_down(self):
		if self.last_contact == 0:
			self.last_contact = time.time()
		value = int(time.time() - self.last_contact)
		globals.data[self.hostname]['delay'] = value

	def connection_up(self):
		self.last_contact == 0
		globals.data[self.hostname]['delay'] = self.last_contact

	def is_dead(self):
		if globals.data[self.hostname]['delay'] > 300:
			return True
		return False

	def handle_funeral(self):
		self.online = False
		globals.active.remove(self.hostname)
		if not self.data['pdu']:
			del globals.data[self.hostname]
			prGreen(f"[{self.hostname}] is offline")
			return
		prGreen(f"[{self.hostname}] is offline but has pdu")
		self.data['delay'] = 'OFF'
		self.data['dead_flag'] = True

class pdu_api:
		actions = ['on', 'off']

		def cmd(action, target, socket):
			if action not in pdu_api.actions:
				return False, 'Invalid action'

			if target.startswith('npower'):
				map = {"on": 1, "off": 0}
				max_socket = 4
				params = {}
				url = f"http://{target}/set.cmd?user=admin+pass=12345678+cmd=setpower+p6{socket}={map[action]}"

			if target.startswith('pdu'):
				map = {"on": 0, "off": 1}
				max_socket = 8
				params = {}
				params[f"outlet{int(socket) - 1}"] = 1
				params["op"] = map[action]
				url = f"http://{target}/control_outlet.htm"

			if int(socket) not in range(1, max_socket + 1):
				prRed('[pdu_api] Error: socket out of range')
				return False, 'socket out of range'
			try:
				response = requests.get(url, params)
			except:
				prRed('[pdu_api] Error: request failure')
				return False, 'Request failed'
			prGreen(f"[pdu_api] {target}::{socket} cmd {action}")
			return True, 'Success'

		def handle(action, target):
			try:
				if not globals.data[target]['pdu']:
					return False, 'No pdu found'
				target, socket = globals.data[target]['pdu'].split('::')
				return pdu_api.cmd(action, target, socket)
			except:
				pass
			return False,'Error: pdu invalid'

class cache:
	pass#cache state.json here and meta.json


#main here
def main():
	print('Multimon V4')
	config.load()
	claim_handler.load()
	thread_handler.start()
	web_server()

def uut_handler(hostname):
	#pyprctl.set_name(hostname)
	uut = uut_connector(hostname)
	while uut.online:
		uut.update_state()
		if uut.is_dead():
			uut.handle_funeral()
		time.sleep(1)
	print(f"{hostname} is dead")

def web_server():
	prYellow(f"[web_server] Starting webserver on port {globals.port}")
	@route('/')
	def handle_root():
		"""
		print('active')
		prBlue(globals.active)
		print('claims')
		prBlue(globals.claims)
		print('claimed_pdus')
		prYellow(globals.pdu_claims)
		"""
		return static_file('index.html', root='./static')

	@route('/static/<filename>')
	def handle_static(filename):
		print('static static')
		return static_file(filename, root='./static')

	@route('/state.json')
	def handle_get_state():
		response.content_type = 'application/json'
		response.body = json.dumps(globals.data, ) #Add caching here!
		return response

	@route('/meta.json')
	def handle_get_state():
		response.content_type = 'application/json'
		response.body = json.dumps({'topography': globals.topography, 'table_keys': globals.table_keys})
		return response

	@route('/hosts')
	def handle_hosts():
		buffer = f'#hosts file generated by multimon on {datetime.now()}\n'
		for idx, uut in globals.data.items():
			buffer += f"{uut['ip']} {uut['uut_name']}\n"
		response.body = buffer
		response.content_type = 'text/plain'
		response.status = 200
		return response

	@route('/consoles')
	def handle_consoles():
		buffer = f'#tty file generated by multimon on {datetime.now()}\n'
		for uut, tty in sorted(globals.tty_connections.items()):
			buffer += f'{uut} {tty}\n'
		response.body = buffer
		response.content_type = 'text/plain'
		response.status = 200
		return response

	@route('/endpoint', method='POST')
	def handle_endpoint():
		print('handle endpoint')

		msg = request.json
		action = msg['action']
		print(msg)
		if action == 'on':
			result, status = pdu_api.handle(**msg)
		if action == 'off':
			result, status = pdu_api.handle(**msg)

		if action == 'claim':
			result, status = claim_handler.claim(**msg)
		if action == 'erase':
			result, status = claim_handler.erase(**msg)

		response.status = 200
		if not result:
			response.status = 400
		returned = {}
		returned['action'] = action
		returned['result'] = result
		returned['status'] = status

		response.content_type = 'application/json'
		response.body = json.dumps(returned)
		return response

	run(host='0.0.0.0', port=globals.port, quiet=True)

def prRed(skk): print("\033[91m{}\033[00m" .format(skk))
def prGreen(skk): print("\033[92m{}\033[00m" .format(skk))
def prYellow(skk): print("\033[93m{}\033[00m" .format(skk))
def prPurple(skk): print("\033[95m{}\033[00m" .format(skk))
def prCyan(skk): print("\033[96m{}\033[00m" .format(skk))
def prBlue(skk): print("\033[94m{}\033[00m" .format(skk))

main()

