#!/usr/bin/env python3
"""
Token-only Zeabur status checker with endpoint fallback.

Usage:
  python check_server_status.py --env-file .env
  python check_server_status.py --zeabur-token sk-xxx --service-id service-xxxxxxxx
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


DEFAULT_ENDPOINTS = [
    "https://api.zeabur.com/graphql",
    "https://api.zeabur.cn/graphql",
]


def load_env_file(path: str):
    if not path or not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()


def post_graphql(endpoint: str, token: str, query: str):
    req = urllib.request.Request(
        endpoint,
        data=json.dumps({"query": query}).encode("utf-8"),
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8", "replace"))


def gql_with_fallback(token: str, query: str, endpoints):
    last_error = None
    for endpoint in endpoints:
        try:
            _, data = post_graphql(endpoint, token, query)
            return endpoint, data
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            # Commonly blocked endpoint in some networks.
            if e.code == 403 and "1010" in body:
                last_error = f"{endpoint}: HTTP 403 error code 1010"
                continue
            last_error = f"{endpoint}: HTTP {e.code} {body[:300]}"
        except Exception as e:
            last_error = f"{endpoint}: {repr(e)}"
    raise RuntimeError(last_error or "All endpoints failed")


def normalize_service_id(value: str):
    if not value:
        return ""
    return value.removeprefix("service-").strip()


def main():
    parser = argparse.ArgumentParser(description="Check Zeabur server/project/service status via API token only.")
    parser.add_argument("--zeabur-token", help="Zeabur API token (sk-xxx)")
    parser.add_argument("--env-file", default=".env", help="Path to .env file (default: .env)")
    parser.add_argument("--service-id", help="Optional service id. Supports both service-xxxx and raw _id.")
    args = parser.parse_args()

    load_env_file(args.env_file)
    token = args.zeabur_token or os.environ.get("ZEABUR_TOKEN")
    if not token:
        print("Error: missing ZEABUR_TOKEN (set in .env or --zeabur-token).")
        sys.exit(1)

    # Step 1: verify token and pick reachable endpoint
    endpoint, me_data = gql_with_fallback(token, "query{me{username}}", DEFAULT_ENDPOINTS)
    if "errors" in me_data:
        print(f"Error: token check failed: {me_data['errors'][0].get('message')}")
        sys.exit(1)
    username = me_data["data"]["me"]["username"]
    print(f"API endpoint: {endpoint}")
    print(f"Token owner: {username}")

    # Step 2: dedicated servers (server-level state in schema is not stable across versions)
    _, servers_data = gql_with_fallback(token, "query{servers{_id name ip}}", [endpoint])
    if "errors" in servers_data:
        print(f"Servers query error: {servers_data['errors'][0].get('message')}")
        sys.exit(1)
    servers = servers_data["data"].get("servers", [])
    print(f"\nDedicated servers: {len(servers)}")
    for s in servers:
        print(f"- {s.get('_id')} | {s.get('name')} | {s.get('ip')}")

    # Step 3: projects + service runtime status
    projects_query = (
        "query{projects{edges{node{_id name "
        "services{_id name status domains{domain}} "
        "environments{_id name}}}}}"
    )
    _, projects_data = gql_with_fallback(token, projects_query, [endpoint])
    if "errors" in projects_data:
        print(f"Projects query error: {projects_data['errors'][0].get('message')}")
        sys.exit(1)

    edges = projects_data["data"]["projects"]["edges"]
    print(f"\nProjects: {len(edges)}")
    for edge in edges:
        p = edge["node"]
        envs = p.get("environments", [])
        env_label = ",".join([f"{e.get('_id')}({e.get('name')})" for e in envs]) if envs else "(none)"
        print(f"- {p.get('_id')} | {p.get('name')} | envs: {env_label}")
        for svc in p.get("services", []):
            domains = [d.get("domain") for d in (svc.get("domains") or []) if d.get("domain")]
            domains_label = ",".join(domains) if domains else "(none)"
            print(f"  service {svc.get('_id')} | {svc.get('name')} | {svc.get('status')} | domains: {domains_label}")

    # Step 4: optional target service lookup
    target_sid = normalize_service_id(args.service_id or "")
    if not target_sid:
        return

    print(f"\nTarget service lookup: {target_sid}")
    found = False
    for edge in edges:
        p = edge["node"]
        env_id = p.get("environments", [{}])[0].get("_id") if p.get("environments") else None
        for svc in p.get("services", []):
            if svc.get("_id") == target_sid:
                found = True
                print(f"project_id: {p.get('_id')}")
                print(f"project_name: {p.get('name')}")
                print(f"service_name: {svc.get('name')}")
                print(f"service_status: {svc.get('status')}")
                print(f"environment_id: {env_id or '(none)'}")
                break
        if found:
            break
    if not found:
        print("Result: service not found in current token scope.")


if __name__ == "__main__":
    main()
