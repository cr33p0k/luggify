# Railway Staging

## Services

Create three Railway services in one project:

1. `postgres`
   Use Railway PostgreSQL.

2. `server`
   - Root directory: `server`
   - Dockerfile path: `Railway.dockerfile`
   - Public networking: enabled

3. `client`
   - Root directory: `client`
   - Dockerfile path: `Railway.dockerfile`
   - Public networking: enabled

## Server variables

Set these on the `server` service:

- `DATABASE_URL`
  Use the PostgreSQL service reference that Railway provides.
- `CORS_ALLOWED_ORIGINS`
  Example:
  `http://localhost:5173,http://localhost:5174,https://<client-domain>`

Optional:

- `CORS_ALLOWED_ORIGIN_REGEX`
  Default already allows `*.vercel.app` and `*.up.railway.app`.

## Client variables

Set this on the `client` service:

- `VITE_API_URL`
  Example:
  `https://<server-domain>`

## Notes

- The client Dockerfile builds a production Vite bundle and serves it with `serve`.
- The server Dockerfile runs Alembic migrations before starting FastAPI.
- After both public domains are issued, update `CORS_ALLOWED_ORIGINS` on the server with the real client domain if needed.
