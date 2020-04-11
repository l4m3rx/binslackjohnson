CONTAINERNAME = binslackjohnson

.PHONY: status build start up down rm shell logs ps ip push

all: status
run: start
status: ps
restart: stop start

build: Dockerfile
	docker-compose build

push:
	docker-compose push

start:
	docker-compose start

up:
	docker-compose up -d

down:
	docker-compose down

stop:
	docker-compose stop
	#docker stop ${CONTAINERNAME}

rm: stop
	docker-compose -rm -f -v
	docker rm ${CONTAINERNAME}

shell:
	docker exec -it ${CONTAINERNAME} /bin/bash

logs:
	docker logs ${CONTAINERNAME}

tail:
	docker-compose logs -f --tail=50

ps:
	@docker ps -f name=${CONTAINERNAME}
	@echo
	@docker-compose ps

ip:
	docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${CONTAINERNAME}

