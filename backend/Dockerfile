# slim = Debian minus build tools and docs (~150MB vs ~1GB for the full image)
FROM python:3.12-slim

WORKDIR /app

# Copy ONLY requirements.txt first. Docker caches each instruction as a layer;
# as long as requirements.txt is unchanged, rebuilds skip the slow pip install
# and only re-copy your source code. Same trick as copying package.json
# before `npm install` in a Node Dockerfile.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# --reload watches for file changes (dev only). docker-compose mounts the
# source dir over /app, so edits on your Mac restart the server in the container.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
