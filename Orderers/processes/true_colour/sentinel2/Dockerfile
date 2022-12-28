FROM geographica/gdal2:2.4.3

RUN apt-get update && apt-get install -y \
  python3-pip vim

ENV PYTHONUNBUFFERED 1

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY ../common/gdal_*.py /usr/bin/

RUN mkdir -p scripts/

COPY Main.py ../common/common.py scripts/

ENTRYPOINT ["/usr/bin/python3", "scripts/Main.py"]
