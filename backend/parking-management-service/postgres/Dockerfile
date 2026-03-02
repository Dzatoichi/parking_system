FROM postgres:16

RUN apt-get update && \
    apt-get install -y postgresql-server-dev-16 git build-essential && \
    git clone https://github.com/pgvector/pgvector.git && \
    cd pgvector && make && make install && \
    cd .. && rm -rf pgvector && \
    apt-get clean