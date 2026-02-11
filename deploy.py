#!/usr/bin/env python3
"""
EasyClaw OpenClaw Deployer
Deploys OpenClaw AI assistant to a Zeabur dedicated server via GraphQL API.

Usage:
    python deploy.py --zeabur-token "sk-xxx" --gateway-token "random32chars" \
        --ai-provider kimi-coding --ai-key "sk-kimi-xxx" \
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
OPENCLAW_IMAGE = "ghcr.io/openclaw/openclaw:2026.2.9"
# Run gateway on 3000. Webhook listener (when enabled) binds to 8787.
GATEWAY_CMD = "node dist/index.js gateway --bind lan --port 3000"


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
    """Verify Zeabur API token by listing projects."""
    data = gql(token, "query{projects{edges{node{_id name}}}}")
    projects = [e["node"] for e in data["projects"]["edges"]]
    print(f"  Token valid. Found {len(projects)} existing project(s).")
    for p in projects:
        print(f"    - {p['name']} ({p['_id']})")
    return "verified"


def find_existing_deployment(token, project_id, service_id, env_id):
    """Verify that the stored deployment IDs are still valid on Zeabur."""
    data = gql(token, f'query{{service(_id:"{service_id}"){{name status}}}}')
    service = data["service"]
    print(f"  Found existing service: {service['name']} ({service['status']})")
    return True  # IDs are valid


def get_server(token: str) -> dict:
    """Find dedicated server."""
    data = gql(token, "query{servers{_id name ip}}")
    servers = data["servers"]
    if not servers:
        raise RuntimeError(
            "No dedicated server found. Please add one in Zeabur dashboard."
        )
    server = servers[0]
    print(f"  Server: {server.get('name', 'N/A')} (IP: {server.get('ip', 'N/A')})")
    print(f"  Region: server-{server['_id']}")
    return server


def create_project(token: str, server_id: str, name: str = "openclaw") -> str:
    """Create project on dedicated server."""
    data = gql(
        token,
        f'mutation{{createProject(region:"server-{server_id}",name:"{name}"){{_id}}}}',
    )
    project_id = data["createProject"]["_id"]
    print(f"  Project ID: {project_id}")
    return project_id


def deploy_template(token: str, project_id: str) -> dict:
    """Deploy OpenClaw template."""
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
                  port: 8787
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
    """Set an environment variable on the service (create or update)."""
    # Mask sensitive values in output
    display = value[:4] + "***" if len(value) > 8 else "***"
    try:
        gql(
            token,
            f'mutation{{createEnvironmentVariable(serviceID:"{service_id}",environmentID:"{env_id}",key:"{key}",value:"{value}"){{key}}}}',
        )
    except RuntimeError as e:
        if "VARIABLE_ALREADY_EXISTS" in str(e):
            # Variable exists — update it via the data Map argument
            gql(
                token,
                f'mutation{{updateEnvironmentVariable(serviceID:"{service_id}",environmentID:"{env_id}",data:{{{key}:"{value}"}})}}',
            )
            print(f"  Updated {key} = {display}")
            return
        raise
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
    brave_api_key: str = None,
    telegram_webhook_url: str = None,
    telegram_webhook_secret: str = None,
    telegram_webhook_path: str = None,
):
    """Configure environment variables."""

    # Required vars
    set_env_var(token, service_id, env_id, "OPENCLAW_GATEWAY_TOKEN", gateway_token)
    set_env_var(token, service_id, env_id, "OPENCLAW_GATEWAY_PORT", "3000")
    set_env_var(token, service_id, env_id, "OPENCLAW_HOME", "/home/node")
    # Avoid mDNS/Bonjour name-length crashes inside containers.
    set_env_var(token, service_id, env_id, "OPENCLAW_DISABLE_BONJOUR", "1")

    # AI provider
    if ai_provider and ai_key:
        provider_map = {
            "kimi-coding": "KIMI_API_KEY",
            "kimi": "KIMI_API_KEY",
            "moonshot": "MOONSHOT_API_KEY",
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
        set_env_var(token, service_id, env_id, "OPENCLAW_TELEGRAM_BOT_TOKEN", telegram_token)
    if telegram_webhook_url:
        set_env_var(token, service_id, env_id, "TELEGRAM_WEBHOOK_URL", telegram_webhook_url)
    if telegram_webhook_secret:
        set_env_var(token, service_id, env_id, "TELEGRAM_WEBHOOK_SECRET", telegram_webhook_secret)
    if telegram_webhook_path:
        set_env_var(token, service_id, env_id, "TELEGRAM_WEBHOOK_PATH", telegram_webhook_path)
    if discord_token:
        set_env_var(token, service_id, env_id, "DISCORD_BOT_TOKEN", discord_token)
    if brave_api_key:
        set_env_var(token, service_id, env_id, "BRAVE_API_KEY", brave_api_key)


def build_config(
    ai_provider=None,
    dm_policy="allowlist",
    telegram_user_id=None,
    telegram_token=None,
    telegram_webhook_url=None,
    telegram_webhook_secret=None,
    telegram_webhook_path=None,
    gateway_token=None,
    gateway_port=3000,
    gateway_bind="lan",
    compact=False,
):
    """Build OpenClaw config dict.

    Note: Do NOT include 'plugins' key — it is invalid in v2026.2.9+.
    Telegram enablement is handled by 'openclaw doctor --fix' in the start command.
    """
    config = {}

    config["agents"] = {"defaults": {"model": {}}}

    # Set primary model based on AI provider
    # kimi-coding = Kimi Coding 國際版 (api.kimi.com, Anthropic-compatible)
    # moonshot = Moonshot Open Platform (api.moonshot.ai, OpenAI-compatible)
    model_map = {
        "kimi-coding": "kimi-coding/k2p5",
        "kimi": "kimi-coding/k2p5",
        "moonshot": "moonshot/kimi-k2.5",
        "anthropic": "anthropic/claude-sonnet-4-5",
        "claude": "anthropic/claude-sonnet-4-5",
        "openai": "openai/gpt-4o",
        "gemini": "google/gemini-2.5-pro",
    }
    model = model_map.get(ai_provider, "kimi-coding/k2p5") if ai_provider else "kimi-coding/k2p5"
    config["agents"]["defaults"]["model"]["primary"] = model

    # Gateway settings (avoid relying on env injection for auth)
    if gateway_token:
        config["gateway"] = {
            "port": gateway_port,
            "mode": "local",
            "bind": gateway_bind,
            "auth": {"mode": "token", "token": gateway_token},
        }

    # Set Telegram channel (DM policy). Bot token comes from env (compact mode).
    config["channels"] = {"telegram": {"dmPolicy": dm_policy}}
    if telegram_token or telegram_webhook_url:
        config["channels"]["telegram"]["enabled"] = True
    if telegram_token:
        config["channels"]["telegram"]["botToken"] = telegram_token
        config["channels"]["telegram"]["tokenFile"] = "/home/node/.openclaw/credentials/telegram/botToken"
        # Block Telegram-initiated config writes for security hardening.
        config["channels"]["telegram"]["configWrites"] = False
        # Disable group messages by default (DM-only hardening).
        config["channels"]["telegram"]["groupPolicy"] = "disabled"
    if telegram_webhook_url:
        config["channels"]["telegram"]["webhookUrl"] = telegram_webhook_url
        if telegram_webhook_secret:
            config["channels"]["telegram"]["webhookSecret"] = telegram_webhook_secret
        if telegram_webhook_path:
            config["channels"]["telegram"]["webhookPath"] = telegram_webhook_path
    if dm_policy == "open":
        config["channels"]["telegram"]["allowFrom"] = ["*"]
    elif dm_policy == "allowlist":
        if telegram_user_id:
            # Use numeric IDs when possible to match OpenClaw docs/examples.
            value = str(telegram_user_id).strip()
            if value.isdigit():
                config["channels"]["telegram"]["allowFrom"] = [value]
            else:
                config["channels"]["telegram"]["allowFrom"] = [value]
        else:
            # No user ID provided — fall back to empty allowlist (nobody can DM)
            config["channels"]["telegram"]["allowFrom"] = []
            print("  Warning: allowlist policy but no --telegram-user-id provided. Nobody will be able to DM the bot.")

    return config


def resolve_provider_id(ai_provider, model_primary):
    """Resolve provider ID used by auth profiles."""
    if model_primary and "/" in model_primary:
        return model_primary.split("/", 1)[0]
    if not ai_provider:
        return None
    provider = ai_provider.lower().strip()
    provider_map = {
        "kimi": "kimi-coding",
        "kimi-coding": "kimi-coding",
        "moonshot": "moonshot",
        "anthropic": "anthropic",
        "claude": "anthropic",
        "openai": "openai",
        "gemini": "google",
        "openrouter": "openrouter",
        "groq": "groq",
    }
    return provider_map.get(provider, provider)


def resolve_ai_env_var(ai_provider):
    """Map AI provider to its env var name."""
    if not ai_provider:
        return None
    provider_map = {
        "kimi-coding": "KIMI_API_KEY",
        "kimi": "KIMI_API_KEY",
        "moonshot": "MOONSHOT_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "groq": "GROQ_API_KEY",
    }
    return provider_map.get(ai_provider.lower())


def update_service_image(token, service_id, env_id, tag):
    """Update Docker image tag (triggers redeployment)."""
    gql(token,
        f'mutation{{updateServiceImage(serviceID:"{service_id}",environmentID:"{env_id}",tag:"{tag}")}}'
    )
    print(f"  Image updated to tag: {tag}")


def save_deployment_ids(env_file, project_id, service_id, env_id, domain):
    """Append deployment IDs to the .env file for future updates."""
    with open(env_file, "a") as f:
        f.write(f"\n# Deployment IDs (auto-generated, do not delete)\n")
        f.write(f"PROJECT_ID={project_id}\n")
        f.write(f"SERVICE_ID={service_id}\n")
        f.write(f"ENVIRONMENT_ID={env_id}\n")
        f.write(f"DOMAIN={domain}\n")


def set_start_command(
    token,
    service_id,
    gateway_token=None,
    ai_provider=None,
    ai_key=None,
    dm_policy="allowlist",
    telegram_user_id=None,
    telegram_token=None,
    telegram_webhook_url=None,
    telegram_webhook_secret=None,
    telegram_webhook_path=None,
):
    """Set startup command with config and doctor --fix.

    The config is written via base64 (updateServiceConfig conflicts with volume
    mounts). 'doctor --fix' auto-enables Telegram and fixes config issues before
    the gateway starts.
    """
    import base64

    config = build_config(
        ai_provider,
        dm_policy,
        telegram_user_id,
        telegram_token,
        telegram_webhook_url,
        telegram_webhook_secret,
        telegram_webhook_path,
        gateway_token,
        3000,
        "lan",
        compact=True,
    )
    config_json = json.dumps(config, separators=(",", ":"))
    config_b64 = base64.b64encode(config_json.encode()).decode()

    # Build shell command parts
    parts = []

    # Ensure OpenClaw reads config from /home/node
    parts.append("export HOME=/home/node")
    parts.append("export OPENCLAW_HOME=/home/node")
    parts.append("export OPENCLAW_CONFIG_PATH=/home/node/.openclaw/openclaw.json")
    parts.append("export OPENCLAW_STATE_DIR=/home/node/.openclaw")
    parts.append("export OPENCLAW_AGENT_DIR=/home/node/.openclaw/agents/main/agent")
    if gateway_token:
        parts.append(f"export OPENCLAW_GATEWAY_TOKEN={gateway_token}")
    parts.append("export OPENCLAW_DISABLE_BONJOUR=1")

    # Write config via base64 (updateServiceConfig makes volume read-only)
    parts.append("mkdir -p /home/node/.openclaw")
    parts.append(f"echo {config_b64} | base64 -d > /home/node/.openclaw/openclaw.json")
    if telegram_token:
        token_b64 = base64.b64encode(telegram_token.encode()).decode()
        parts.append("mkdir -p /home/node/.openclaw/credentials/telegram")
        parts.append(f"echo {token_b64} | base64 -d > /home/node/.openclaw/credentials/telegram/botToken")
    # Ensure auth profile exists for the default agent (required for model responses).
    provider_id = resolve_provider_id(ai_provider, config["agents"]["defaults"]["model"]["primary"])
    if provider_id and ai_key:
        auth_payload = {
            "profiles": {
                f"{provider_id}:default": {
                    "type": "api_key",
                    "provider": provider_id,
                    "key": ai_key,
                }
            }
        }
        auth_js = "\n".join([
            "const fs = require('fs');",
            "const dir = '/home/node/.openclaw/agents/main/agent';",
            "fs.mkdirSync(dir, { recursive: true });",
            f"const payload = {json.dumps(auth_payload, separators=(',', ':'))};",
            "fs.writeFileSync(dir + '/auth-profiles.json', JSON.stringify(payload));",
        ])
        auth_b64 = base64.b64encode(auth_js.encode()).decode()
        parts.append("mkdir -p /home/node/.openclaw")
        parts.append(f"printf %s {auth_b64} | base64 -d > /home/node/.openclaw/write_auth.js")
        parts.append("node /home/node/.openclaw/write_auth.js || true")

    # Pre-configure Telegram plugin/channel before gateway starts.
    gateway_cmd = GATEWAY_CMD
    if gateway_token:
        gateway_cmd = f"{GATEWAY_CMD} --token {gateway_token}"
    gateway_block = " node dist/index.js plugins enable telegram || true;"
    if telegram_token:
        gateway_block += " node dist/index.js channels add --channel telegram --token \"$(cat /home/node/.openclaw/credentials/telegram/botToken)\" || true;"
    gateway_block += f" {gateway_cmd} & GW_PID=$!; sleep 3;"
    gateway_block += " wait $GW_PID"
    parts.append(f"({gateway_block})")

    command = 'sh -c "' + " && ".join(parts) + '"'

    # Escape for GraphQL
    cmd_escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    gql(
        token,
        f'mutation{{updateServiceCommand(serviceID:"{service_id}",command:"{cmd_escaped}")}}',
    )
    print(f"  Model: {ai_provider or 'kimi-coding'}")
    print(f"  DM Policy: {dm_policy}")
    if dm_policy == "allowlist" and telegram_user_id:
        print(f"  Allowed User: {telegram_user_id}")
    print(f"  Gateway: {GATEWAY_CMD}")


def restart_service(token: str, service_id: str, env_id: str):
    """Restart service."""
    gql(
        token,
        f'mutation{{restartService(serviceID:"{service_id}",environmentID:"{env_id}")}}',
    )
    print("  Service restarting...")
    print("  Waiting 30 seconds for startup...")
    time.sleep(30)


def add_domain(token: str, service_id: str, env_id: str, server_id: str, subdomain: str) -> str:
    """Add domain."""
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
    """Verify deployment."""

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


def set_telegram_webhook(bot_token: str, webhook_url: str, webhook_secret: str = None):
    """Configure Telegram webhook for the bot."""
    if not bot_token or not webhook_url:
        return
    try:
        # Clear any existing webhook and pending updates
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/deleteWebhook",
            data={"drop_pending_updates": "true"},
            timeout=20,
        )
        payload = {"url": webhook_url}
        if webhook_secret:
            payload["secret_token"] = webhook_secret
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            data=payload,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram setWebhook failed: {data}")
        print("  Telegram webhook set.")
    except Exception as e:
        print(f"  Warning: Telegram setWebhook failed: {e}")


def clear_telegram_webhook(bot_token: str):
    """Clear Telegram webhook (switch to long polling)."""
    if not bot_token:
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/deleteWebhook",
            data={"drop_pending_updates": "true"},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram deleteWebhook failed: {data}")
        print("  Telegram webhook cleared (long polling).")
    except Exception as e:
        print(f"  Warning: Telegram deleteWebhook failed: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Deploy OpenClaw AI assistant to Zeabur dedicated server"
    )
    parser.add_argument("--zeabur-token", help="Zeabur API token (sk-xxx)")
    parser.add_argument("--gateway-token", help="Gateway auth token (>=32 chars, auto-generated if omitted)")
    parser.add_argument("--project-name", default="openclaw", help="Project name (default: openclaw)")
    parser.add_argument("--ai-provider", help="AI provider: kimi-coding, moonshot, anthropic, openai, gemini, groq")
    parser.add_argument("--ai-key", help="AI provider API key")
    parser.add_argument("--telegram-token", help="Telegram Bot token")
    parser.add_argument("--telegram-webhook-url", help="Telegram webhook URL (enables webhook mode)")
    parser.add_argument("--telegram-webhook-secret", help="Telegram webhook secret (X-Telegram-Bot-Api-Secret-Token)")
    parser.add_argument("--telegram-webhook-path", help="Telegram webhook path (default: /telegram-webhook)")
    parser.add_argument("--discord-token", help="Discord Bot token")
    parser.add_argument("--subdomain", help="Subdomain for zeabur.app (auto-generated if omitted)")
    parser.add_argument("--dm-policy", default="allowlist", choices=["pairing", "open", "allowlist", "disabled"],
                        help="Telegram DM access policy (default: allowlist — only specified user can DM)")
    parser.add_argument("--telegram-user-id", help="Telegram user ID for allowlist DM policy (required when dm-policy=allowlist)")
    parser.add_argument("--env-file", help="Load settings from .env file")
    parser.add_argument("--force-new", action="store_true", help="Force new deployment even if IDs exist")

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
        args.ai_key = args.ai_key or os.environ.get("KIMI_API_KEY") or os.environ.get("MOONSHOT_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
        args.telegram_token = args.telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        args.telegram_user_id = args.telegram_user_id or os.environ.get("TELEGRAM_USER_ID")
        args.telegram_webhook_url = args.telegram_webhook_url or os.environ.get("TELEGRAM_WEBHOOK_URL")
        args.telegram_webhook_secret = args.telegram_webhook_secret or os.environ.get("TELEGRAM_WEBHOOK_SECRET")
        args.telegram_webhook_path = args.telegram_webhook_path or os.environ.get("TELEGRAM_WEBHOOK_PATH")
        args.subdomain = args.subdomain or os.environ.get("SUBDOMAIN")
        args.brave_api_key = os.environ.get("BRAVE_API_KEY") or None
        if os.environ.get("KIMI_API_KEY"):
            args.ai_provider = args.ai_provider or "kimi-coding"
        elif os.environ.get("MOONSHOT_API_KEY"):
            args.ai_provider = args.ai_provider or "moonshot"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            args.ai_provider = args.ai_provider or "anthropic"
        elif os.environ.get("OPENAI_API_KEY"):
            args.ai_provider = args.ai_provider or "openai"

    # Read deployment IDs from env
    args.project_id = os.environ.get("PROJECT_ID")
    args.service_id = os.environ.get("SERVICE_ID")
    args.environment_id = os.environ.get("ENVIRONMENT_ID")
    args.domain = os.environ.get("DOMAIN")

    if args.domain and args.telegram_webhook_path and not args.telegram_webhook_url:
        args.telegram_webhook_url = f"https://{args.domain}{args.telegram_webhook_path}"

    # Validate zeabur token
    if not args.zeabur_token:
        print("Error: --zeabur-token is required (or set ZEABUR_TOKEN in .env)")
        sys.exit(1)

    # Ensure brave_api_key attr exists when not loading from env file
    if not hasattr(args, "brave_api_key"):
        args.brave_api_key = None

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

    # Webhook defaults
    if args.telegram_webhook_url and not args.telegram_webhook_secret:
        args.telegram_webhook_secret = secrets.token_hex(16)
        masked = args.telegram_webhook_secret[:4] + "***"
        print(f"Generated Telegram webhook secret: {masked}")
    if args.telegram_webhook_url and not args.telegram_webhook_path:
        args.telegram_webhook_path = "/telegram-webhook"

    # Determine mode
    is_update = (args.project_id and args.service_id and args.environment_id
                 and not args.force_new)

    print("=" * 60)
    if is_update:
        print("  EasyClaw OpenClaw Deployer (UPDATE MODE)")
    else:
        print("  EasyClaw OpenClaw Deployer (NEW DEPLOYMENT)")
    print("=" * 60)

    try:
        if is_update:
            # ===== UPDATE MODE =====
            project_id = args.project_id
            service_id = args.service_id
            env_id = args.environment_id
            domain = args.domain

            # Step 1: Verify token
            step(1, "Verifying Zeabur API Token")
            verify_token(args.zeabur_token)

            # Step 2: Verify existing deployment
            step(2, "Verifying Existing Deployment")
            find_existing_deployment(args.zeabur_token, project_id, service_id, env_id)

            # Step 3: Configure env vars
            step(3, "Updating Environment Variables")
            configure_service(
                args.zeabur_token,
                service_id,
                env_id,
                args.gateway_token,
                args.ai_provider,
                args.ai_key,
                args.telegram_token,
                args.discord_token,
                args.brave_api_key,
                args.telegram_webhook_url,
                args.telegram_webhook_secret,
                args.telegram_webhook_path,
            )

            # Step 4: Set start command with config
            step(4, "Setting Config & Start Command")
            set_start_command(
                args.zeabur_token,
                service_id,
                args.gateway_token,
                args.ai_provider,
                args.ai_key,
                args.dm_policy,
                args.telegram_user_id,
                args.telegram_token,
                args.telegram_webhook_url,
                args.telegram_webhook_secret,
                args.telegram_webhook_path,
            )

            # Step 5: Update image
            image_tag = OPENCLAW_IMAGE.split(":")[-1]
            step(5, f"Updating Image to {image_tag}")
            update_service_image(args.zeabur_token, service_id, env_id, image_tag)

            # Step 6: Restart
            step(6, "Restarting Service")
            restart_service(args.zeabur_token, service_id, env_id)

            # Step 7: Configure Telegram webhook (optional)
            if args.telegram_webhook_url:
                step(7, "Configuring Telegram Webhook")
                set_telegram_webhook(
                    args.telegram_token,
                    args.telegram_webhook_url,
                    args.telegram_webhook_secret,
                )
                next_step = 8
            else:
                step(7, "Clearing Telegram Webhook (Long Polling)")
                clear_telegram_webhook(args.telegram_token)
                next_step = 8

            # Verify
            step(next_step, "Verifying Deployment")
            if domain:
                verify_deployment(args.zeabur_token, project_id, service_id, env_id, domain)
            else:
                print("  No domain stored — skipping HTTP check")
                data = gql(args.zeabur_token, f'query{{service(_id:"{service_id}"){{name status}}}}')
                print(f"  Service status: {data['service']['status']}")

            # Summary
            print("\n" + "=" * 60)
            print("  UPDATE SUMMARY")
            print("=" * 60)
            print(f"  Mode:        Update (in-place)")
            if domain:
                print(f"  Control UI:  https://{domain}")
                print(f"  WebChat:     https://{domain}/__openclaw__/webchat/")
            print(f"  Project ID:  {project_id}")
            print(f"  Service ID:  {service_id}")
            print(f"  AI Provider: {args.ai_provider or 'kimi-coding'}")
            print(f"  DM Policy:   {args.dm_policy}")
            print("=" * 60)

        else:
            # ===== NEW DEPLOYMENT MODE =====

            # Step 1: Verify token
            step(1, "Verifying Zeabur API Token")
            verify_token(args.zeabur_token)

            # Step 2: Find server
            step(2, "Finding Dedicated Server")
            server = get_server(args.zeabur_token)

            # Step 3: Create project
            step(3, "Creating Project")
            project_id = create_project(args.zeabur_token, server["_id"], args.project_name)

            # Step 4: Deploy template
            step(4, "Deploying OpenClaw")
            ids = deploy_template(args.zeabur_token, project_id)
            service_id = ids["service_id"]
            env_id = ids["environment_id"]

            # Step 5: Configure env vars
            step(5, "Configuring Environment Variables")
            configure_service(
                args.zeabur_token,
                service_id,
                env_id,
                args.gateway_token,
                args.ai_provider,
                args.ai_key,
                args.telegram_token,
                args.discord_token,
                args.brave_api_key,
                args.telegram_webhook_url,
                args.telegram_webhook_secret,
                args.telegram_webhook_path,
            )

            # Step 6: Add domain
            step(6, "Adding Domain")
            domain = add_domain(
                args.zeabur_token,
                service_id,
                env_id,
                server["_id"],
                args.subdomain,
            )

            # Step 7: Set webhook env vars only if provided (default: long polling)
            step(7, "Setting Webhook Environment Variables (optional)")
            if args.telegram_webhook_url:
                set_env_var(args.zeabur_token, service_id, env_id, "TELEGRAM_WEBHOOK_URL", args.telegram_webhook_url)
                if args.telegram_webhook_secret:
                    set_env_var(args.zeabur_token, service_id, env_id, "TELEGRAM_WEBHOOK_SECRET", args.telegram_webhook_secret)
                if args.telegram_webhook_path:
                    set_env_var(args.zeabur_token, service_id, env_id, "TELEGRAM_WEBHOOK_PATH", args.telegram_webhook_path)
            else:
                print("  Webhook not configured (long polling).")

            # Step 8: Set start command with config (now includes webhook URL)
            step(8, "Setting Config & Start Command")
            set_start_command(
                args.zeabur_token,
                service_id,
                args.gateway_token,
                args.ai_provider,
                args.ai_key,
                args.dm_policy,
                args.telegram_user_id,
                args.telegram_token,
                args.telegram_webhook_url,
                args.telegram_webhook_secret,
                args.telegram_webhook_path,
            )

            # Step 9: Restart to pick up config changes
            step(9, "Restarting Service")
            restart_service(args.zeabur_token, service_id, env_id)

            # Step 10: Configure Telegram webhook (optional)
            if args.telegram_webhook_url:
                step(10, "Configuring Telegram Webhook")
                set_telegram_webhook(
                    args.telegram_token,
                    args.telegram_webhook_url,
                    args.telegram_webhook_secret,
                )
                next_step = 11
            else:
                step(10, "Clearing Telegram Webhook (Long Polling)")
                clear_telegram_webhook(args.telegram_token)
                next_step = 11

            # Verify
            step(next_step, "Verifying Deployment")
            verify_deployment(args.zeabur_token, project_id, service_id, env_id, domain)

            # Save deployment IDs to .env for future updates
            if args.env_file:
                save_deployment_ids(args.env_file, project_id, service_id, env_id, domain)
                print(f"\n  Deployment IDs saved to {args.env_file}")
                print(f"  Next run will use UPDATE mode automatically.")

            # Summary
            print("\n" + "=" * 60)
            print("  DEPLOYMENT SUMMARY")
            print("=" * 60)
            print(f"  Mode:        New deployment")
            print(f"  Control UI:  https://{domain}")
            print(f"  WebChat:     https://{domain}/__openclaw__/webchat/")
            print(f"  Gateway Token: {args.gateway_token}")
            print(f"  Project ID:  {project_id}")
            print(f"  Service ID:  {service_id}")
            if args.telegram_token:
                bot_username = "your_bot"  # User needs to check @BotFather
                print(f"  Telegram:    https://t.me/{bot_username}")
            print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
