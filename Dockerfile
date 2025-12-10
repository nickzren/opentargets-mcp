# Use a suitable Python base image
FROM python:3.12-slim

# Copy requirements / project
COPY . .

# Install dependencies
RUN pip install --no-cache-dir uv --upgrade \
    && uv sync

# Default command
CMD ["uv","run","python","-m","opentargets_mcp.server"]
