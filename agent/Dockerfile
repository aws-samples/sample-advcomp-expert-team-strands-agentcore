FROM public.ecr.aws/docker/library/python:3.10-slim

WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp

# Copy agent code
COPY . .

# Expose port for AgentCore Runtime
EXPOSE 8080

# Set OpenTelemetry environment variables
ENV OTEL_PYTHON_DISTRO=aws_distro
ENV OTEL_PYTHON_CONFIGURATOR=aws_configurator
ENV OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group=/agents/advcomp-swarm-logs,x-aws-log-stream=default,x-aws-metric-namespace=agents
ENV OTEL_RESOURCE_ATTRIBUTES=service.name=advcomp_swarm
ENV AGENT_OBSERVABILITY_ENABLED=true

# Run the advcomp swarm agent
CMD ["python", "advcomp_swarm.py"]