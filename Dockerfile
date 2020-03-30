FROM python:3-alpine

WORKDIR /bot
ADD . /bot
RUN pip3 install -r requirements.txt

CMD ["python", "/bot/binslackjohnson.py"]
