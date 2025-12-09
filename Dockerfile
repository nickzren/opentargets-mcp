# Use a suitable Python base image
FROM python:3.12-slim

# Set workdir
WORKDIR /app

# Copy requirements / project
COPY . .

# Install dependencies
RUN pip install --no-cache-dir uv --upgrade \
    && uv sync \
    && pip install --no-cache-dir .

# Default command
CMD ["uv","run","python","-m","opentargets_mcp.server"]
