FROM python:3.7-slim

RUN apt-get update && apt-get install -y iproute2 && rm -rf /var/lib/apt/lists/*


ENV PYTHONUNBUFFERED=1
ENV LOCAL_PATH="/vol1/1000/disk1/Media"
ENV STRM_PREFIX="/vol1/1000/netdisk/cd2/CloudDrive"
ENV EMBY_URL="http://127.0.0.1:8096"
ENV EMBY_API_KEY="c91c6cccb105413bb32fc5c023f0c1cc"

WORKDIR /app

EXPOSE 18122

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python3", "-u", "app/strm.py" ]
