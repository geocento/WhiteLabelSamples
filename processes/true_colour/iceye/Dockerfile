FROM osgeo/gdal:ubuntu-small-3.5.2

RUN apt-get update && apt-get install -y \
  python3-pip vim

ENV PYTHONUNBUFFERED 1

COPY ./iceye/requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY ./common/gdal_*.py /usr/bin/

RUN mkdir -p scripts/
RUN mkdir -p scripts/data

COPY ./iceye/Main.py ./common/generic.py scripts/

COPY ./iceye/data/* scripts/data/

WORKDIR scripts/

ENTRYPOINT ["/usr/bin/python3", "Main.py"]
