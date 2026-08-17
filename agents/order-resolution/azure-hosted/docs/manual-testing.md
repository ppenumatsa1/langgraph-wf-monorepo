# Manual Testing

## Local

```bash
make up
curl -fsS http://localhost:5173/health
curl -fsS http://localhost:5173/api/health
API_URL=http://localhost:5173 make manual-matrix
make test-e2e
```

Verify `ORD-1001` completes without HITL, `ORD-1004` pauses and completes after
approval, and `ORD-1009` follows the high-value approval path. Confirm the SSE
event names and that Workflow History never receives HTML for an API request.

## Azure-hosted

After deployment, obtain `frontend_url` from release verification evidence:

```bash
PLAYWRIGHT_BASE_URL=https://<frontend-fqdn> make test-e2e
scripts/manual/run-manual-matrix.sh https://<frontend-fqdn> \
  --case ORD-1001 --case ORD-1004 --case ORD-1009
```

The backend FQDN is internal-only. Validate frontend `/health`, proxied
`/api/health`, immutable images, one active healthy revision per app,
Application Insights correlation for all three thread IDs, and no exceptions.
