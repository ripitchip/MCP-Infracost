FROM mcr.microsoft.com/devcontainers/python:3.12

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Node.js (utile pour MCP)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Install Terraform and tflint
RUN curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor | tee /usr/share/keyrings/hashicorp-archive-keyring.gpg > /dev/null \
    && echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list \
    && apt-get update \
    && apt-get install -y terraform

RUN curl -fsSL https://github.com/terraform-linters/tflint/releases/download/v0.48.0/tflint_linux_amd64.zip -o /tmp/tflint.zip \
    && cd /tmp \
    && unzip tflint.zip \
    && mv tflint /usr/local/bin/ \
    && rm tflint.zip

WORKDIR /workspaces