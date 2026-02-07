#!/usr/bin/env python3
"""
EasyClaw OpenClaw Deployer
Deploys OpenClaw AI assistant to a Zeabur dedicated server via GraphQL API.

Usage:
    python deploy.py --zeabur-token "sk-xxx" --gateway-token "random32chars" \
        --ai-provider moonshot --ai-key "sk-kimi-xxx" \
        --telegram-token "123:ABC" --subdomain "my-bot"

Or with .env file:
    cp .env.example .env
    # Edit .env with your values
    python deploy.py --env-file .env
"""

import argparse
import json
import os
import secrets
import sys
import time

try:
    import requests
except ImportError:
    print("Error: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

API_URL = "https://api.zeabur.com/graphql"
OPENCLAW_IMAGE = "ghcr.io/openclaw/openclaw:2026.2.2"
GATEWAY_CMD = "node dist/index.js gateway --allow-unconfigured --bind lan"


def gql(token: str, query: str) -> dict:
    """Execute a GraphQL query against Zeabur API."""
    r = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"query": query},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {json.dumps(data['errors'], indent=2)}")
    return data["data"]


def step(n: int, msg: str):
    print(f"\n{'='*60}")
    print(f"  Step {n}: {msg}")
    print(f"{'='*60}")


def verify_token(token: str) -> str:
    """Step 1: Verify Zeabur API token and return username."""
    step(1, "Verifying Zeabur API Token")
    data = gql(token, "query{user{name username}}")
    user = data["user"]
    print(f"  Authenticated as: {user['username']} ({user['name']})")
    return user["username"]


def get_server(token: str) -> dict:
    """Step 2: Find dedicated server."""
    step(2, "Finding Dedicated Server")
    data = gql(token, "query{servers{_id hostname status ip}}")
    servers = data["servers"]
    if not servers:
        raise RuntimeError(
            "No dedicated server found. Please add one in Zeabur dashboard."
        )
    # Pick the first online server
    server = None
    for s in servers:
        if s.get("status") == "online":
            server = s
            break
    if not server:
        server = servers[0]
        print(f"  Warning: No online server found, using: {server['hostname']}")
    print(f"  Server: {server['hostname']} (IP: {server.get('ip', 'N/A')})")
    print(f"  Status: {server['status']}")
    print(f"  Region: server-{server['_id']}")
    return server


def create_project(token: str, server_id: str, name: str = "openclaw") -> str:
    """Step 3: Create project on dedicated server."""
    step(3, "Creating Project")
    data = gql(
        token,
        f'mutation{{createProject(region:"server-{server_id}",name:"{name}"){{_id}}}}',
    )
    project_id = data["createProject"]["_id"]
    print(f"  Project ID: {project_id}")
    return project_id


def deploy_template(token: str, project_id: str) -> dict:
    """Step 4: Deploy OpenClaw template."""
    step(4, "Deploying OpenClaw")
    yaml_content = f"""apiVersion: zeabur.com/v1
kind: Template
metadata:
    name: OpenClaw-EasyClaw
spec:
    description: OpenClaw AI Assistant deployed by EasyClaw
    services:
        - name: openclaw
          template: PREBUILT
          spec:
            source:
                image: {OPENCLAW_IMAGE}
            ports:
                - id: web
                  port: 3000
                  type: HTTP
            env:
                NODE_ENV:
                    default: production
            volumes:
                - id: openclaw-data
                  dir: /home/node/.openclaw"""

    # Escape for GraphQL string
    yaml_escaped = yaml_content.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    data = gql(
        token,
        f'mutation{{deployTemplate(projectID:"{project_id}",rawSpecYaml:"{yaml_escaped}"){{_id}}}}',
    )
    print(f"  Deployed successfully")

    # Get service and environment IDs
    time.sleep(2)
    proj_data = gql(
        token,
        f'query{{project(_id:"{project_id}"){{services{{_id name}} environments{{_id name}}}}}}',
    )
    project = proj_data["project"]
    service = project["services"][0]
    env = project["environments"][0]
    print(f"  Service: {service['name']} ({service['_id']})")
    print(f"  Environment: {env['name']} ({env['_id']})")
    return {"service_id": service["_id"], "environment_id": env["_id"]}


def set_env_var(token: str, service_id: str, env_id: str, key: str, value: str):
    """Set an environment variable on the service."""
    gql(
        token,
        f'mutation{{createEnvironmentVariable(serviceID:"{service_id}",environmentID:"{env_id}",key:"{key}",value:"{value}"){{key}}}}',
    )
    # Mask sensitive values in output
    display = value[:4] + "***" if len(value) > 8 else "***"
    print(f"  Set {key} = {display}")


def configure_service(
    token: str,
    service_id: str,
    env_id: str,
    gateway_token: str,
    ai_provider: str = None,
    ai_key: str = None,
    telegram_token: str = None,
    discord_token: str = None,
):
    """Step 5: Configure environment variables."""
    step(5, "Configuring Environment Variables")

    # Required vars
    set_env_var(token, service_id, env_id, "OPENCLAW_GATEWAY_TOKEN", gateway_token)
    set_env_var(token, service_id, env_id, "OPENCLAW_GATEWAY_PORT", "3000")

    # AI provider
    if ai_provider and ai_key:
        provider_map = {
            "moonshot": "MOONSHOT_API_KEY",
            "kimi": "MOONSHOT_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "groq": "GROQ_API_KEY",
        }
        env_key = provider_map.get(ai_provider.lower())
        if env_key:
            set_env_var(token, service_id, env_id, env_key, ai_key)
        else:
            print(f"  Warning: Unknown AI provider '{ai_provider}', setting as OPENAI_API_KEY")
            set_env_var(token, service_id, env_id, "OPENAI_API_KEY", ai_key)

    # Communication channels
    if telegram_token:
        set_env_var(token, service_id, env_id, "TELEGRAM_BOT_TOKEN", telegram_token)
    if discord_token:
        set_env_var(token, service_id, env_id, "DISCORD_BOT_TOKEN", discord_token)


def build_start_command(ai_provider: str = None, dm_policy: str = "pairing") -> str:
    """Build the start command with embedded config generation."""
    config = {"agents": {"defaults": {"model": {}}}}

    # Set primary model based on AI provider
    model_map = {
        "moonshot": "moonshot/kimi-k2.5",
        "kimi": "moonshot/kimi-k2.5",
        "anthropic": "anthropic/claude-sonnet-4-5",
        "claude": "anthropic/claude-sonnet-4-5",
        "openai": "openai/gpt-4o",
        "gemini": "google/gemini-2.5-pro",
    }
    model = model_map.get(ai_provider, "moonshot/kimi-k2.5") if ai_provider else "moonshot/kimi-k2.5"
    config["agents"]["defaults"]["model"]["primary"] = model

    # Set Telegram DM policy
    config["channels"] = {"telegram": {"dmPolicy": dm_policy}}
    if dm_policy == "open":
        config["channels"]["telegram"]["allowFrom"] = ["*"]

    config_json = json.dumps(config).replace('"', '\\"')
    return f'sh -c "mkdir -p /root/.openclaw && echo \\"{config_json}\\" > /root/.openclaw/openclaw.json && {GATEWAY_CMD}"'


def set_start_command(token: str, service_id: str, ai_provider: str = None, dm_policy: str = "pairing"):
    """Step 6: Set startup command with config."""
    step(6, "Setting Start Command")
    command = build_start_command(ai_provider, dm_policy)
    # Escape for GraphQL
    cmd_escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    gql(
        token,
        f'mutation{{updateServiceCommand(serviceID:"{service_id}",command:"{cmd_escaped}")}}',
    )
    print(f"  Model: {ai_provider or 'moonshot'}")
    print(f"  DM Policy: {dm_policy}")
    print(f"  Gateway: --bind lan --allow-unconfigured")


def restart_service(token: str, service_id: str, env_id: str):
    """Step 7: Restart service."""
    step(7, "Restarting Service")
    gql(
        token,
        f'mutation{{restartService(serviceID:"{service_id}",environmentID:"{env_id}")}}',
    )
    print("  Service restarting...")
    print("  Waiting 30 seconds for startup...")
    time.sleep(30)


def add_domain(token: str, service_id: str, env_id: str, server_id: str, subdomain: str) -> str:
    """Step 8: Add domain."""
    step(8, "Adding Domain")
    # Check availability
    data = gql(
        token,
        f'mutation{{checkDomainAvailable(domain:"{subdomain}",isGenerated:true,region:"server-{server_id}"){{isAvailable reason}}}}',
    )
    check = data["checkDomainAvailable"]
    if not check["isAvailable"]:
        # Try with random suffix
        subdomain = f"{subdomain}-{secrets.token_hex(3)}"
        print(f"  Domain unavailable, trying: {subdomain}")
        data = gql(
            token,
            f'mutation{{checkDomainAvailable(domain:"{subdomain}",isGenerated:true,region:"server-{server_id}"){{isAvailable reason}}}}',
        )
        check = data["checkDomainAvailable"]
        if not check["isAvailable"]:
            raise RuntimeError(f"Domain '{subdomain}' unavailable: {check['reason']}")

    # Add domain
    data = gql(
        token,
        f'mutation{{addDomain(serviceID:"{service_id}",environmentID:"{env_id}",isGenerated:true,domain:"{subdomain}"){{domain}}}}',
    )
    domain = data["addDomain"]["domain"]
    print(f"  Domain: https://{domain}")
    return domain


def verify_deployment(token: str, project_id: str, service_id: str, env_id: str, domain: str):
    """Step 9: Verify deployment."""
    step(9, "Verifying Deployment")

    # Check service status
    data = gql(token, f'query{{service(_id:"{service_id}"){{name status}}}}')
    status = data["service"]["status"]
    print(f"  Service status: {status}")

    # Check logs
    data = gql(
        token,
        f'query{{runtimeLogs(projectID:"{project_id}",serviceID:"{service_id}",environmentID:"{env_id}"){{message timestamp}}}}',
    )
    logs = data["runtimeLogs"]
    gateway_ok = any("listening on ws://" in l["message"] for l in logs)
    telegram_ok = any("telegram" in l["message"].lower() for l in logs)

    print(f"  Gateway started: {'Yes' if gateway_ok else 'No (check logs)'}")
    print(f"  Telegram connected: {'Yes' if telegram_ok else 'Not detected yet'}")

    # Test HTTP
    try:
        r = requests.get(f"https://{domain}/", timeout=10)
        print(f"  Web UI: HTTP {r.status_code} {'OK' if r.status_code == 200 else 'ERROR'}")
    except Exception as e:
        print(f"  Web UI: Error - {e}")

    if status == "RUNNING" and gateway_ok:
        print("\n  Deployment SUCCESSFUL!")
    else:
        print("\n  Deployment may need attention. Check logs:")
        for l in logs[:5]:
            print(f"    {l['timestamp']} | {l['message'][:100]}")


def main():
    parser = argparse.ArgumentParser(
        description="Deploy OpenClaw AI assistant to Zeabur dedicated server"
    )
    parser.add_argument("--zeabur-token", required=True, help="Zeabur API token (sk-xxx)")
    parser.add_argument("--gateway-token", help="Gateway auth token (>=32 chars, auto-generated if omitted)")
    parser.add_argument("--project-name", default="openclaw", help="Project name (default: openclaw)")
    parser.add_argument("--ai-provider", help="AI provider: moonshot, anthropic, openai, gemini, groq")
    parser.add_argument("--ai-key", help="AI provider API key")
    parser.add_argument("--telegram-token", help="Telegram Bot token")
    parser.add_argument("--discord-token", help="Discord Bot token")
    parser.add_argument("--subdomain", help="Subdomain for zeabur.app (auto-generated if omitted)")
    parser.add_argument("--dm-policy", default="pairing", choices=["pairing", "open", "allowlist", "disabled"],
                        help="Telegram DM access policy (default: pairing)")
    parser.add_argument("--env-file", help="Load settings from .env file")

    args = parser.parse_args()

    # Load from .env file if specified
    if args.env_file and os.path.exists(args.env_file):
        print(f"Loading settings from {args.env_file}")
        with open(args.env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()
        args.zeabur_token = args.zeabur_token or os.environ.get("ZEABUR_TOKEN")
        args.gateway_token = args.gateway_token or os.environ.get("GATEWAY_TOKEN")
        args.ai_key = args.ai_key or os.environ.get("MOONSHOT_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
        args.telegram_token = args.telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        args.subdomain = args.subdomain or os.environ.get("SUBDOMAIN")
        if os.environ.get("MOONSHOT_API_KEY"):
            args.ai_provider = args.ai_provider or "moonshot"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            args.ai_provider = args.ai_provider or "anthropic"
        elif os.environ.get("OPENAI_API_KEY"):
            args.ai_provider = args.ai_provider or "openai"

    # Auto-generate gateway token if not provided
    if not args.gateway_token:
        args.gateway_token = secrets.token_hex(32)  # 64 hex chars
        print(f"Generated gateway token: {args.gateway_token}")

    # Validate gateway token length
    if len(args.gateway_token) < 32:
        print(f"Warning: Gateway token is {len(args.gateway_token)} chars. Recommended: >=32 chars.")

    # Auto-generate subdomain if not provided
    if not args.subdomain:
        args.subdomain = f"oc-{secrets.token_hex(4)}"

    print("=" * 60)
    print("  EasyClaw OpenClaw Deployer")
    print("=" * 60)

    try:
        # Step 1: Verify token
        username = verify_token(args.zeabur_token)

        # Step 2: Find server
        server = get_server(args.zeabur_token)

        # Step 3: Create project
        project_id = create_project(args.zeabur_token, server["_id"], args.project_name)

        # Step 4: Deploy template
        ids = deploy_template(args.zeabur_token, project_id)

        # Step 5: Configure env vars
        configure_service(
            args.zeabur_token,
            ids["service_id"],
            ids["environment_id"],
            args.gateway_token,
            args.ai_provider,
            args.ai_key,
            args.telegram_token,
            args.discord_token,
        )

        # Step 6: Set start command with config
        set_start_command(args.zeabur_token, ids["service_id"], args.ai_provider, args.dm_policy)

        # Step 7: Restart
        restart_service(args.zeabur_token, ids["service_id"], ids["environment_id"])

        # Step 8: Add domain
        domain = add_domain(
            args.zeabur_token,
            ids["service_id"],
            ids["environment_id"],
            server["_id"],
            args.subdomain,
        )

        # Step 9: Verify
        verify_deployment(
            args.zeabur_token, project_id, ids["service_id"], ids["environment_id"], domain
        )

        # Summary
        print("\n" + "=" * 60)
        print("  DEPLOYMENT SUMMARY")
        print("=" * 60)
        print(f"  Control UI:  https://{domain}")
        print(f"  WebChat:     https://{domain}/__openclaw__/webchat/")
        print(f"  Gateway Token: {args.gateway_token}")
        print(f"  Project ID:  {project_id}")
        print(f"  Service ID:  {ids['service_id']}")
        if args.telegram_token:
            bot_username = "your_bot"  # User needs to check @BotFather
            print(f"  Telegram:    https://t.me/{bot_username}")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
