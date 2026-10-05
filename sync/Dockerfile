# The sync job is the published cognee image plus the GitLab connector.
# Nothing else changes: same cognee, same GLiNER runtime, same user.
FROM cognee/cognee:main

# Branch tarball, not git+https: the image has no git. Point this at the merged
# connector (upstream tag or your fork) when it lands.
ARG CONNECTOR_ARCHIVE=https://github.com/cluing-ai/cognee-community/archive/refs/heads/feat/gitlab-connector.tar.gz

USER root
# --no-deps: cognee, dlt and requests are already in the image; the connector
# must not replace a package under the running venv.
RUN /app/.venv/bin/python -m ensurepip --upgrade >/dev/null 2>&1 || true \
 && /app/.venv/bin/python -m pip install --no-cache-dir --no-deps \
      "${CONNECTOR_ARCHIVE}#subdirectory=packages/connector/gitlab"
COPY sync.py healthcheck.py /app/sync/
RUN chown -R cognee:cognee /app/sync
USER cognee

ENTRYPOINT ["/app/.venv/bin/python", "/app/sync/sync.py"]
