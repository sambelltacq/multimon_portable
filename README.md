# multimon_portable
## Web status monitor for a fleet of ACQ400 systems on LAN

### Typical Screenshot:

![Screenshot](https://github.com/D-TACQ/multimon_portable/releases/download/v1.0.0/Screenshot.from.2023-04-07.16-58-31.png "Screenshot")

### A large fleet of units under test earlier:
https://github.com/D-TACQ/multimon_portable/releases/download/v1.0.0/Screenshot.from.2020-08-18.08-59-06.png

Prerequisites:
* python3 packages: bottle requests xml2dict
* we assume there is a working DNS
* Multimon uses EPICS beacons to detect new devices, however we wanted to avoid needing to install EPICS on the host, and also to make the appropriate firewall entry, instead:
* Multimon needs to know the name of a "lighthouse" : a first ACQ400 system to get a TCP socket feed of all EPICS beacon data
* For production, use redirection from a webserver on the same box (nginx example shown below)
* for initial testing, it's quicket to use the embedded webserver and a local browser
  * Add the lighthouse initial HOSTNAME in config.json
  * Open firewall port:
    ```
	#On centos7
	sudo firewall-cmd --zone=public --add-port=5000/tcp --permanent
	sudo firewall-cmd --reload

	#On Ubuntu
	sudo ufw allow 5000/tcp
    ```

  * then just run it:
  ```
  	[peter@andros multimon_portable]$ ./multimon.py
	Multimon V4
	[config] Loading config.json
	[claim_handler] Added 7 claims
	[web_server] Starting webserver on port 5000
	[casw] acq2006_015 is lighthouse
	[casw] Connected to acq2006_015 casw
	[thread_handler] New uut acq1001_070
  ...
  ```
  * then connect a local web browser to localhost:5000/,



To run as service do:
```
      sudo cp multimon.service /etc/systemd/system/
      sudo systemctl daemon-reload
      sudo systemctl enable multimon
      sudo systemctl start multimon
```
Nginx config:
```
      location /multimon {
      	return 302 $scheme://$host:5000/;
      }
```
