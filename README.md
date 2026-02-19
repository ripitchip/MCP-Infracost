# MCP-server

This project implements a Model Context Protocol (MCP) server that provides cost estimation for infrastructure as code (IaC) configurations using Infracost. The server exposes an API endpoint that accepts IaC configurations and returns cost estimates based on the provided data.

> [!WARNING]
> This project is an academic exercise and is not intended for production use. It may contain security vulnerabilities and should be used with caution.

## Installation

Clone the repository and navigate to the project directory:

```bash
git clone https://github.com/ripitchip/MCP-Infracost.git
cd MCP-Infracost
```

Three environment variables are available to run the server:

- `INFRACOST_API_KEY`: Your Infracost API key (required)
- `INFRACOST_API_URL`: The URL of the Infracost API (optional, defaults to `https://pricing.api.infracost.io/graphql`)
- `GITHUB_TOKEN`: A GitHub token for authenticated API requests (optional, but recommended)

Write your environment variables in a `.env` file in the root of the project. You can use the provided `.env.example` as a template.

```bash
cp .env.example .env
nano .env
```

We use `uv` to manage our Python environment and dependencies. Install the required dependencies:

```bash
uv pip install -e .
```

## Starting the services

To launch the fastapi/mcp:

```bash
uv run main.py
```

To launch the mcp inspector:

```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
```

![Inspector page](image.png)

To launch the terraform readme fetcher:

```bash
uv run scripts/fetch_terraform_readmes.py
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
