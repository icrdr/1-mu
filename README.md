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
or
`gunicorn -w 2 -b 0:8000 app:app`
`sudo fuser -k 8000/tcp`
### nginx
```
location /api {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
  
location /download {
    alias /var/www/1-mu/download/;
}

location /upload {
    alias /var/www/1-mu/upload/;
}
```


# support emoji store
### create database
CREATE DATABASE database_name CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

sqlalchemy mysql url setting
mysql+mysqlconnector://{username}:{password}@{hostname}/{databasename}?charset=utf8mb4

edit /etc/mysql/my.cnf
```
[client]
default-character-set = utf8mb4
[mysql]
default-character-set = utf8mb4
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
init_connect='SET NAMES utf8mb4'
```
`etc/init.d/mysql` restart