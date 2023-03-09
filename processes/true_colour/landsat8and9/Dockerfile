FROM osgeo/gdal:ubuntu-small-3.5.2

RUN apt-get update && apt-get install -y \
  python3-pip vim

ENV PYTHONUNBUFFERED 1

COPY ./landsat8and9/requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

COPY ./common/gdal_*.py /usr/bin/

RUN mkdir -p scripts/

COPY ./landsat8and9/Main.py ./common/generic.py scripts/

ENTRYPOINT ["/usr/bin/python3", "scripts/Main.py"]
