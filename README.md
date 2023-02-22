# multimon_portable
Multimonitor for d-tacq acqs

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
