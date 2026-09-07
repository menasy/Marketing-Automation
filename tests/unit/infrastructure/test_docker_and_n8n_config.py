"""Unit tests for Dockerfile, docker-compose.yml, and n8n workflow.json configuration contracts."""

import json
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]


class TestDockerfileConfig:
    """Validation tests for Dockerfile directives, non-root user security, and healthcheck."""

    def test_dockerfile_exists_and_non_empty(self) -> None:
        """Verify Dockerfile exists at repository root and has content."""
        dockerfile_path = REPO_ROOT / "Dockerfile"
        assert dockerfile_path.is_file(), "Dockerfile must exist at repository root"
        content = dockerfile_path.read_text(encoding="utf-8")
        assert len(content.strip()) > 0, "Dockerfile must not be empty"

    def test_dockerfile_base_image_and_env(self) -> None:
        """Verify Dockerfile specifies python:3.11-slim and unbuffered Python env vars."""
        dockerfile_path = REPO_ROOT / "Dockerfile"
        content = dockerfile_path.read_text(encoding="utf-8")

        assert "FROM python:3.11-slim" in content
        assert "PYTHONUNBUFFERED=1" in content
        assert "PYTHONDONTWRITEBYTECODE=1" in content
        assert "PIP_NO_CACHE_DIR=1" in content

    def test_dockerfile_non_root_user_security(self) -> None:
        """Verify Dockerfile creates and switches to non-root appuser (UID/GID 10001)."""
        dockerfile_path = REPO_ROOT / "Dockerfile"
        content = dockerfile_path.read_text(encoding="utf-8")

        assert "10001" in content
        assert "appuser" in content
        assert "USER appuser" in content

    def test_dockerfile_system_deps_and_healthcheck(self) -> None:
        """Verify curl installation, apt list cleaning, healthcheck, and uvicorn command."""
        dockerfile_path = REPO_ROOT / "Dockerfile"
        content = dockerfile_path.read_text(encoding="utf-8")

        assert "curl" in content
        assert "rm -rf /var/lib/apt/lists/*" in content
        assert "HEALTHCHECK" in content
        assert "http://localhost:8000/health" in content
        assert "uvicorn" in content
        assert "src.presentation.api.app:app" in content


class TestDockerComposeConfig:
    """Validation tests for docker-compose.yml YAML syntax, services, and volume bindings."""

    def test_docker_compose_valid_yaml(self) -> None:
        """Verify docker-compose.yml parses as valid YAML."""
        compose_path = REPO_ROOT / "docker-compose.yml"
        assert compose_path.is_file(), "docker-compose.yml must exist at repository root"

        with compose_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert isinstance(data, dict), "docker-compose.yml must parse into a dictionary"
        assert "services" in data, "docker-compose.yml must define 'services'"

    def test_docker_compose_api_service_configuration(self) -> None:
        """Verify API service configuration, volumes, ports, and healthcheck."""
        compose_path = REPO_ROOT / "docker-compose.yml"
        with compose_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        services = data.get("services", {})
        assert "api" in services, "docker-compose.yml must define 'api' service"
        api = services["api"]

        assert api.get("container_name") == "marketing_automation_api"
        assert "8000:8000" in api.get("ports", [])

        volumes = [str(v) for v in api.get("volumes", [])]
        assert any("./data:/app/data:ro" in v for v in volumes)
        assert any("./output:/app/output:rw" in v for v in volumes)

        assert "healthcheck" in api

    def test_n8n_entrypoint_script_exists_and_executable(self) -> None:
        """Verify automation/entrypoint-n8n.sh exists and has executable permissions."""
        script_path = REPO_ROOT / "automation" / "entrypoint-n8n.sh"
        assert script_path.is_file(), "automation/entrypoint-n8n.sh must exist"
        assert os.access(script_path, os.X_OK), "automation/entrypoint-n8n.sh must be executable"

    def test_docker_compose_n8n_service_configuration(self) -> None:
        """Verify n8n service, zero-touch entrypoint, credentials, and dependencies."""
        compose_path = REPO_ROOT / "docker-compose.yml"
        compose_content = compose_path.read_text(encoding="utf-8")

        with compose_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        services = data.get("services", {})
        assert "n8n" in services, "docker-compose.yml must define 'n8n' service"
        n8n = services["n8n"]

        assert n8n.get("container_name") == "marketing_automation_n8n"
        assert "5678:5678" in n8n.get("ports", [])

        env_list = n8n.get("environment", [])
        env_str = str(env_list)
        assert "GENERIC_TIMEZONE=Europe/Istanbul" in env_str or "TZ=Europe/Istanbul" in env_str
        assert "N8N_BLOCK_ENV_ACCESS_IN_NODE=false" in env_str
        assert "N8N_ADMIN_EMAIL=${N8N_ADMIN_EMAIL:-}" in env_str or "N8N_ADMIN_EMAIL" in env_str
        assert (
            "N8N_ADMIN_PASSWORD=${N8N_ADMIN_PASSWORD:-}" in env_str
            or "N8N_ADMIN_PASSWORD" in env_str
        )

        # Check zero-touch entrypoint configuration
        entrypoint = n8n.get("entrypoint")
        entrypoint_str = str(entrypoint)
        assert "/automation/entrypoint-n8n.sh" in entrypoint_str

        # Assert fragile publish:workflow command is completely removed
        assert "publish:workflow" not in compose_content, (
            "docker-compose.yml must not contain deprecated publish:workflow command"
        )
        assert "command" not in n8n, "docker-compose.yml n8n service must rely on entrypoint script"

        # Check dependency on API healthcheck
        depends_on = n8n.get("depends_on", {})
        assert "api" in depends_on
        assert depends_on["api"].get("condition") == "service_healthy"


class TestN8nWorkflowConfig:
    """Validation tests for automation/workflow.json schema, triggers, and HTTP API caller."""

    def test_workflow_json_valid(self) -> None:
        """Verify automation/workflow.json parses as valid JSON."""
        workflow_path = REPO_ROOT / "automation" / "workflow.json"
        assert workflow_path.is_file(), "automation/workflow.json must exist"

        data = json.loads(workflow_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert data.get("active") is True
        assert "nodes" in data
        assert "connections" in data

    def test_workflow_json_triggers_and_endpoints(self) -> None:
        """Verify Cron trigger (08:00 Europe/Istanbul), Manual trigger, and HTTP API endpoint."""
        workflow_path = REPO_ROOT / "automation" / "workflow.json"
        data = json.loads(workflow_path.read_text(encoding="utf-8"))
        nodes = data.get("nodes", [])

        # 1. Cron Trigger check
        cron_node = next(
            (n for n in nodes if n.get("type") == "n8n-nodes-base.scheduleTrigger"), None
        )
        assert cron_node is not None, "Workflow must contain a scheduleTrigger node"
        rule = cron_node["parameters"]["rule"]["interval"][0]
        assert rule["expression"] == "0 8 * * *"

        # 2. Manual Trigger check
        manual_node = next(
            (n for n in nodes if n.get("type") == "n8n-nodes-base.manualTrigger"), None
        )
        assert manual_node is not None, "Workflow must contain a manualTrigger node"

        # 3. HTTP Request Node check
        http_node = next((n for n in nodes if n.get("type") == "n8n-nodes-base.httpRequest"), None)
        assert http_node is not None, "Workflow must contain an httpRequest node"
        params = http_node.get("parameters", {})
        assert params.get("method") == "POST"
        assert params.get("url") == "http://api:8000/api/v1/pipeline/run"

    def test_workflow_json_no_hardcoded_secrets(self) -> None:
        """Verify zero hardcoded API keys or secret tokens in workflow node parameters."""
        workflow_path = REPO_ROOT / "automation" / "workflow.json"
        content = workflow_path.read_text(encoding="utf-8")

        assert "AIzaSy" not in content, "No Google API keys should be hardcoded in workflow.json"
        assert "xoxb-" not in content, "No Slack bot tokens should be hardcoded in workflow.json"
        assert "sk-proj-" not in content, "No OpenAI keys should be hardcoded in workflow.json"


class TestAutomationReadmeConfig:
    """Validation tests for automation/README.md runbook & architecture docs."""

    def test_automation_readme_exists_and_non_empty(self) -> None:
        """Verify automation/README.md exists and contains over 50 lines of documentation."""
        readme_path = REPO_ROOT / "automation" / "README.md"
        assert readme_path.is_file(), "automation/README.md must exist"

        lines = readme_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 50, f"automation/README.md must have >= 50 lines, got {len(lines)}"

    def test_automation_readme_contains_required_tokens_and_architecture(self) -> None:
        """Verify presence of cron, timezone, endpoints, slack channel, and diagrams."""
        readme_path = REPO_ROOT / "automation" / "README.md"
        content = readme_path.read_text(encoding="utf-8")

        # Required tokens
        assert "0 8 * * *" in content
        assert "Europe/Istanbul" in content
        assert "http://api:8000/api/v1/pipeline/run" in content
        assert "SLACK_WEBHOOK_URL" in content
        assert "#marketing-alerts-critical" in content

        # Architectural separation statement
        assert "Statement of Architectural Separation" in content
        assert "ZERO business logic" in content

        # Required operational sections
        assert "Node-by-Node Specification" in content
        assert "Zero-Touch Auto-Import" in content
        assert "Environment Variables" in content
        assert "Testing & Verification Runbook" in content
