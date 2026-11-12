# Fast Downward classical planner, built from a pinned upstream release.
#
#   docker build -t fast-downward:latest docker/fast-downward
#
# Pinning the release keeps the planner experiment reproducible: rebuilding the
# image months later yields the same search code and therefore the same plans.

ARG FD_RELEASE=release-24.06.1

# --- build stage -------------------------------------------------------------
FROM ubuntu:22.04 AS build
ARG FD_RELEASE
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates cmake g++ git make python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /fast-downward
RUN git clone --depth 1 --branch "${FD_RELEASE}" https://github.com/aibasel/downward.git . \
    && ./build.py release \
    && strip --strip-all builds/release/bin/downward

# --- runtime stage -----------------------------------------------------------
FROM ubuntu:22.04
ARG FD_RELEASE
LABEL org.opencontainers.image.title="fast-downward" \
      org.opencontainers.image.description="Fast Downward planner for the VisionLeader campus domain" \
      org.opencontainers.image.version="${FD_RELEASE}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /fast-downward
COPY --from=build /fast-downward/fast-downward.py .
COPY --from=build /fast-downward/driver ./driver
COPY --from=build /fast-downward/builds/release/bin ./builds/release/bin
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh && mkdir -p /pddl

ENV PATH="/fast-downward:${PATH}"
ENTRYPOINT ["/fast-downward/entrypoint.sh"]
