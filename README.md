# multimon_portable
## Web status monitor for a fleet of ACQ400 systems on LAN

### Typical Screenshot:

![Screenshot](https://github.com/D-TACQ/multimon_portable/releases/download/v1.0.0/Screenshot.from.2023-04-07.16-58-31.png "Screenshot")

### A large fleet of units under test earlier:
https://github.com/D-TACQ/multimon_portable/releases/download/v1.0.0/Screenshot.from.2020-08-18.08-59-06.png

Prerequisites:
* python3 packages: flask requests xml2dict
* we assume there is a working DNS
* Multimon uses EPICS beacons to detect new devices, however we wanted to avoid needing to install EPICS on the host, and also to make the appropriate firewall entry, instead:
* Multimon needs to know the name of a "lighthouse" : a first ACQ400 system to get a TCP socket feed of all EPICS beacon data
* For production, use redirection from a webserver on the same box (nginx example shown below)
* for initial testing, it's quicket to use the embedded webserver and a local browser
  * Add the lighthouse initial HOSTNAME in config.json
  * then just run it:
  ```
  [peter@andros multimon_portable]$ ./multimon.py
  casw server established acq2006_015
  * Serving Flask app "multimon" (lazy loading)
  * Environment: production
    WARNING: This is a development server. Do not use it in a production deployment.
    Use a production WSGI server instead.
  *  Debug mode: off
  Adding acq2206_001
  Adding acq2106_387
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
        proxy_pass http://127.0.0.1:5000/;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Prefix /multimon;
      }
```
Apache config:
```
      <Proxy /mulitmon>
        Order deny,allow
        Allow from all
      </Proxy>
      
      ProxyPass /multimon http://localhost:5000
      ProxyPassReverse /mulitmon http://localhost:5000

```
