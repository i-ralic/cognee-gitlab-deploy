# The sync job is the published cognee image plus the GitLab connector.
# Nothing else changes: same cognee, same GLiNER runtime, same user.
# cognee/cognee:main as pulled on 2026-10-05 (cognee 1.6.2), pinned by digest; same as docker-compose.yml api
FROM cognee/cognee@sha256:b9c727a631222897f60de9d796190bbf0a33254afdb335a6638a2419dccc3101

# Commit tarball, not git+https (the image has no git) and not a branch (branches move); one repo
# name throughout: the connector PR lives in i-ralic/cognee-community.
ARG CONNECTOR_ARCHIVE=https://github.com/i-ralic/cognee-community/archive/dabe353729e96acf41485396e05339c8c203d9c1.tar.gz
# The package version (0.1.0) does not change between connector commits, so the image records the
# archive it was built from: as a label and as a file the proof can read back.
LABEL org.opencontainers.image.source="https://github.com/i-ralic/cognee-gitlab-deploy" \
      io.cognee.connector.archive="${CONNECTOR_ARCHIVE}"

USER root
# --no-deps: cognee, dlt and requests are already in the image; the connector
# must not replace a package under the running venv.
RUN /app/.venv/bin/python -m ensurepip --upgrade >/dev/null 2>&1 || true \
 && /app/.venv/bin/python -m pip install --no-cache-dir --no-deps \
      "${CONNECTOR_ARCHIVE}#subdirectory=packages/connector/gitlab"
COPY sync.py healthcheck.py /app/sync/
RUN echo "${CONNECTOR_ARCHIVE}" > /app/sync/CONNECTOR_ARCHIVE \
 && mkdir -p /app/.cognee && chown -R cognee:cognee /app/sync /app/.cognee
USER cognee

ENTRYPOINT ["/app/.venv/bin/python", "/app/sync/sync.py"]
