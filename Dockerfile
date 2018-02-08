# DESCRIPTION: This is a development Dockerfile that makes it convenient to make changes to the daemon code.
# USAGE: First, build the image: 
#
#> docker build -t lbry .
#
# Once built, you have a container image that has all the requirements for building and running the LBRY daemon.
# Make your changes to the python code, and then start your container e.g.:
#
#> docker run --rm -v ${PWD}:/lbry -w /lbry -i -p 5279:5279 -p 5678:5678 --name lbry lbry
#
# This activates the image, mounts the host machine's current directory (the working source directory) to /lbry in the container,
# re-initializes and runs the daemon with the new code. 
# It also exposes port 5678 and installs ptvsd so you can attach a remote python debugger from your host machine.
# You can interact with the daemon via curl or through docker CLI:
#
#> docker exec lbry lbrynet-cli wallet_balance
#
# (where lbry is the name of the image you built, and wallet_balance is the daemon CLI command to execute.)

FROM ubuntu:16.04
RUN apt-get update && apt-get install -y build-essential \
    python2.7 \
    python2.7-dev \ 
    python-pip \
    git \
    python-virtualenv \
    libssl-dev \
    libffi-dev \
    python-protobuf

RUN mkdir lbry
WORKDIR /lbry

COPY . /lbry

RUN pip install pylint
RUN pip install ptvsd
RUN pip install -U --no-cache-dir -r requirements.txt
EXPOSE 5279
EXPOSE 5678
CMD pip install --editable . && lbrynet-daemon