# The sync job is the published cognee image plus the GitLab connector.
# Nothing else changes: same cognee, same GLiNER runtime, same user.
FROM cognee/cognee:main

ARG CONNECTOR_REF=feat/gitlab-connector
ARG CONNECTOR_REPO=https://github.com/cluing-ai/cognee-community.git

USER root
# --no-deps: cognee, dlt and requests are already in the image; the connector
# must not replace a package under the running venv.
RUN /app/.venv/bin/python -m ensurepip --upgrade >/dev/null 2>&1 || true \
 && /app/.venv/bin/python -m pip install --no-cache-dir --no-deps \
      "git+${CONNECTOR_REPO}@${CONNECTOR_REF}#subdirectory=packages/connector/gitlab"
COPY sync.py healthcheck.py /app/sync/
RUN chown -R cognee:cognee /app/sync
USER cognee

ENTRYPOINT ["/app/.venv/bin/python", "/app/sync/sync.py"]
