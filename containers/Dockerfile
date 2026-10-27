# Resolve and commit an immutable base digest using scripts/lock-container.sh before a release.
ARG BASE_IMAGE=python@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d
FROM ${BASE_IMAGE}
ARG TARGETARCH
ARG PLINK_DATE=20250609
RUN test "$TARGETARCH" = amd64
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl unzip bzip2 make gcc libbz2-dev liblzma-dev libcurl4-openssl-dev \
    libssl-dev zlib1g-dev procps awscli && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl --fail --location --retry 2 --max-time 120 https://github.com/samtools/bcftools/releases/download/1.21/bcftools-1.21.tar.bz2 -o b.tar.bz2 \
 && echo '528a4cc1d3555368db75a700b22a3c95da893fd1827f6d304716dfd45ea4e282  b.tar.bz2' | sha256sum -c - && tar -xf b.tar.bz2 && cd bcftools-1.21 && make -j2 && make install
RUN curl --fail --location --retry 2 --max-time 120 https://github.com/samtools/samtools/releases/download/1.21/samtools-1.21.tar.bz2 -o s.tar.bz2 \
 && echo '05724b083a6b6f0305fcae5243a056cc36cf826309c3cb9347a6b89ee3fc5ada  s.tar.bz2' | sha256sum -c - && tar -xf s.tar.bz2 && cd samtools-1.21 && ./configure --without-curses && make -j2 && make install
RUN curl --fail --location --retry 2 --max-time 120 https://s3.amazonaws.com/plink2-assets/alpha6/plink2_linux_x86_64_${PLINK_DATE}.zip -o p.zip \
 && echo 'd316e13f09a95099b562df49618cd102f06c61a74a9d6416cfdca34566908065  p.zip' | sha256sum -c - && unzip p.zip plink2 -d /usr/local/bin && rm -rf /build/*
WORKDIR /opt/riceflow
COPY pyproject.toml requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock pytest==8.4.2
COPY src/ src/
COPY tests/ tests/
COPY scripts/fixtures.py scripts/fixtures.py
RUN pip install --no-deps . && python scripts/fixtures.py \
 && plink2 --version && bcftools --version && samtools --version
ENV PYTHONUNBUFFERED=1
WORKDIR /work
