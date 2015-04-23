FROM mozillamarketplace/centos-mysql-mkt:0.2

RUN yum install -y supervisor

RUN mkdir -p /pip/{cache,build}
ADD requirements /pip/requirements
WORKDIR /pip
RUN pip install --find-links https://pyrepo.addons.mozilla.org/ peep
RUN peep install -b /pip/build --download-cache /pip/cache --no-deps -r /pip/requirements/dev.txt --find-links https://pyrepo.addons.mozilla.org/
