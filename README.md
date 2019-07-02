# 1-mu
python 3.x

### env:
```
"FLASK_APP": "app",
"FLASK_ENV": "production",
"SECRET_KEY": [your app secret key],
"DATABASE_URL": [your database url]
```

flask run

flask init

flask update

### supervisor:
`/etc/supervisor/conf.d/`
```
command=/root/Envs/emu/bin/gunicorn -w 2 -b 0:5000 app:app
directory=/var/www/1-mu
autostart=true
autorestart=true
user=root
environment=FLASK_APP=app,FLASK_ENV=production,SECRET_KEY=,DATABASE_URL
stdout_logfile=/var/log/supervisor/gunicorn_supervisor.log
stderr_logfile=/var/log/supervisor/gunicorn_supervisor_err.log
```
To enable the configuration, run the following commands:
```
$ sudo supervisorctl reread
$ sudo service supervisor restart
```

