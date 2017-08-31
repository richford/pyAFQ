###############################################################################
# Dockerfile to build pyAFQ Application Container
# Based on python 3 image
###############################################################################

# Use official Python runtime as base image
FROM python:3

# File Author / Maintainer
MAINTAINER "Adam Richie-Halford" richiehalford@gmail.com

# Install git so that we can get pyAFQ from its github repo
RUN apt-get update
RUN apt-get install -y git

# Install pyAFQ dependencies
COPY requirements.txt /tmp/
RUN pip install --requirement /tmp/requirements.txt

# Install pyAFQ from its github repo
RUN pip install git+git://github.com/yeatmanlab/pyAFQ.git@master#egg=pyAFQ

# Create a default user. Available via runtime flag `--user afq-user`
# Add user to 'staff' group.
# Give user a home directory.
RUN useradd afq-user \
    && addgroup afq-user staff \
    && mkdir /home/afq-user \
    && chown -R afq-user:staff /home/afq-user

ENV HOME /home/afq-user

# Copy the python script and its dependencies
COPY pyafq_hcp/src/run_pyafq.py /home/afq-user/
COPY common_utils /home/afq-user/common_utils

WORKDIR /home/afq-user

ENTRYPOINT ["python", "/home/afq-user/run_pyafq.py"]
