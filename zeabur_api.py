"""
Zeabur GraphQL API Client
A lightweight wrapper for common Zeabur API operations.

Usage:
    from zeabur_api import ZeaburClient
    client = ZeaburClient("sk-your-token")
    client.verify()
    servers = client.list_servers()
"""

import json
import requests


class ZeaburClient:
    API_URL = "https://api.zeabur.com/graphql"

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _gql(self, query: str) -> dict:
        r = requests.post(
            self.API_URL,
            headers=self.headers,
            json={"query": query},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL error: {json.dumps(data['errors'], indent=2)}")
        return data["data"]

    # === User ===
    def verify(self) -> dict:
        """Verify token and return user info."""
        return self._gql("query{user{name username}}")["user"]

    # === Servers ===
    def list_servers(self) -> list:
        """List all dedicated servers."""
        return self._gql("query{servers{_id hostname status ip}}")["servers"]

    # === Projects ===
    def create_project(self, region: str, name: str = "openclaw") -> str:
        """Create project and return project ID."""
        data = self._gql(f'mutation{{createProject(region:"{region}",name:"{name}"){{_id}}}}')
        return data["createProject"]["_id"]

    def list_projects(self) -> list:
        """List all projects with services and domains."""
        data = self._gql(
            "query{projects{edges{node{_id name services{_id name status domains{domain}} environments{_id name}}}}}"
        )
        return [edge["node"] for edge in data["projects"]["edges"]]

    # === Services ===
    def get_service(self, service_id: str) -> dict:
        """Get service details."""
        return self._gql(f'query{{service(_id:"{service_id}"){{name status}}}}')["service"]

    def update_command(self, service_id: str, command: str) -> bool:
        """Update service start command."""
        return self._gql(f'mutation{{updateServiceCommand(serviceID:"{service_id}",command:"{command}")}}')["updateServiceCommand"]

    def restart(self, service_id: str, env_id: str) -> bool:
        """Restart a service."""
        return self._gql(f'mutation{{restartService(serviceID:"{service_id}",environmentID:"{env_id}")}}')["restartService"]

    # === Environment Variables ===
    def set_env(self, service_id: str, env_id: str, key: str, value: str) -> dict:
        """Create an environment variable."""
        # Escape value for GraphQL
        value_escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return self._gql(
            f'mutation{{createEnvironmentVariable(serviceID:"{service_id}",environmentID:"{env_id}",key:"{key}",value:"{value_escaped}"){{key value}}}}'
        )["createEnvironmentVariable"]

    def update_env(self, service_id: str, env_id: str, key: str, value: str):
        """Update an existing environment variable."""
        value_escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return self._gql(
            f'mutation{{updateEnvironmentVariable(serviceID:"{service_id}",environmentID:"{env_id}",data:{{{key}:"{value_escaped}"}})}}'
        )["updateEnvironmentVariable"]

    # === Domains ===
    def check_domain(self, subdomain: str, region: str) -> dict:
        """Check if a subdomain is available."""
        return self._gql(
            f'mutation{{checkDomainAvailable(domain:"{subdomain}",isGenerated:true,region:"{region}"){{isAvailable reason}}}}'
        )["checkDomainAvailable"]

    def add_domain(self, service_id: str, env_id: str, subdomain: str) -> str:
        """Add a generated zeabur.app subdomain. Returns full domain."""
        data = self._gql(
            f'mutation{{addDomain(serviceID:"{service_id}",environmentID:"{env_id}",isGenerated:true,domain:"{subdomain}"){{domain}}}}'
        )
        return data["addDomain"]["domain"]

    def remove_domain(self, domain: str) -> bool:
        """Remove a domain."""
        return self._gql(f'mutation{{removeDomain(domain:"{domain}")}}')["removeDomain"]

    # === Deploy ===
    def deploy_template(self, project_id: str, yaml_content: str) -> dict:
        """Deploy a YAML template."""
        yaml_escaped = yaml_content.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return self._gql(
            f'mutation{{deployTemplate(projectID:"{project_id}",rawSpecYaml:"{yaml_escaped}"){{_id}}}}'
        )["deployTemplate"]

    # === Logs ===
    def runtime_logs(self, project_id: str, service_id: str, env_id: str) -> list:
        """Get runtime logs."""
        data = self._gql(
            f'query{{runtimeLogs(projectID:"{project_id}",serviceID:"{service_id}",environmentID:"{env_id}"){{message timestamp}}}}'
        )
        return data["runtimeLogs"]

    # === Cleanup ===
    def delete_service(self, service_id: str, env_id: str) -> bool:
        """Delete a service."""
        return self._gql(
            f'mutation{{deleteService(serviceID:"{service_id}",environmentID:"{env_id}")}}'
        )["deleteService"]

    def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        return self._gql(f'mutation{{deleteProject(projectID:"{project_id}")}}')["deleteProject"]
