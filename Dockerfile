# For the full stack, see https://github.com/mozilla/payments-env/

FROM mozillamarketplace/centos-mysql-mkt:0.2
RUN yum install -y supervisor
RUN yum install -y bash-completion

RUN mkdir -p /pip/{cache,build}
ADD requirements /pip/requirements
WORKDIR /pip
RUN pip install --find-links https://pyrepo.addons.mozilla.org/ peep
RUN peep install \
    --build /pip/build \
    --download-cache /pip/cache \
    --no-deps -r /pip/requirements/dev.txt \
    --find-links https://pyrepo.addons.mozilla.org/

# Ship the source in the container.
COPY . /srv/payments-service

# Preserve bash history across image updates.
# This works best when you link your local source code
# as a volume.
ENV HISTFILE=/srv/payments-service/docker/artifacts/bash_history
# Configure bash history.
ENV HISTSIZE=50000
ENV HISTIGNORE=ls:exit:"cd .."
# This prevents dupes but only in memory for the current session.
ENV HISTCONTROL=erasedups
