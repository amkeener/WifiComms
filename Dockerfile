FROM python:3.11-slim

WORKDIR /app

# Copy package files
COPY pyproject.toml .
COPY src/ src/

# Install the package
RUN pip install --no-cache-dir -e .

# Default command: listen mode
CMD ["agent-messenger", "listen"]
