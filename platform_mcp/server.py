"""
platform-mcp

An MCP server that exposes platform engineering knowledge as tools an MCP
client (Claude Code, Claude Desktop, Cursor, etc.) can call. Built on the
official MCP Python SDK via FastMCP.

Tools exposed:
  - list_blueprints()                  list reference platform blueprints
  - describe_blueprint(name)           full description of a named blueprint
  - describe_pattern(pattern)          plain-prose explanation of a design pattern
  - get_runbook(scenario)              runbook steps for a common incident
  - check_compliance(component)        compliance check matrix for a component

Every tool call is logged at INFO with the call args, so the audit pitch in
the README has actual code behind it. Logs go to stderr so they don't pollute
the stdio JSON-RPC channel.

Run:
    pip install -e .
    platform-mcp                       # or: python platform_mcp/server.py

Wire into Claude Desktop / Claude Code with the config block in
docs/claude_desktop_config.json.
"""

import logging
import sys
import uuid
from typing import Literal

from mcp.server.fastmcp import FastMCP

# Log to stderr — stdout is the MCP transport, anything we print there
# corrupts the JSON-RPC framing.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s platform-mcp %(message)s",
)
log = logging.getLogger("platform-mcp")

mcp = FastMCP("platform-mcp")


# ---- Knowledge base --------------------------------------------------------
# In production this would be backed by a real source (Git, Confluence, a
# CMDB, Postgres, a vector store). For the demo it lives in plain Python
# data so the server is one file and runs with no external dependencies.

BlueprintName = Literal[
    "idp-banking-blueprint",
    "aks-platform",
    "ml-platform-k8s",
    "gitops-platform-automation",
    "onprem-k8s-blueprint",
]

PatternName = Literal[
    "workload-identity",
    "policy-as-code",
    "multi-tenant-namespaces",
    "gitops-fleet",
]

RunbookScenario = Literal[
    "argocd-out-of-sync",
    "node-pool-pressure",
]

ComponentName = Literal[
    "namespace",
    "image",
]


BLUEPRINTS: dict[str, dict[str, object]] = {
    "idp-banking-blueprint": {
        "summary": "Internal Developer Platform reference for regulated banking on GKE.",
        "stack": ["GKE", "Terraform", "Argo CD", "Sentinel", "OPA", "Workload Identity"],
        "tenants": "multi-tenant via namespaces",
        "audit": "full audit trail via Cloud Audit Logs and Argo CD history",
        "url": "https://github.com/SriLingala/idp-banking-blueprint",
    },
    "aks-platform": {
        "summary": "Production-grade AKS blueprint.",
        "stack": [
            "AKS", "Terraform", "Helm", "Workload Identity", "Key Vault",
            "Prometheus", "cert-manager", "Ingress NGINX", "GitHub Actions",
        ],
        "tenants": "shared platform add-ons across namespaces",
        "audit": "GitHub Actions CI logs, Azure Activity Logs",
        "url": "https://github.com/SriLingala/aks-platform",
    },
    "ml-platform-k8s": {
        "summary": "AKS-based MLOps platform with GPU node pools.",
        "stack": [
            "AKS", "GPU node pools", "MLflow", "Argo Workflows",
            "KServe", "GitOps", "Helm",
        ],
        "tenants": "per-team MLflow experiments and Argo Workflow namespaces",
        "audit": "MLflow tracking server plus Argo Workflows lineage",
        "url": "https://github.com/SriLingala/ml-platform-k8s",
    },
    "gitops-platform-automation": {
        "summary": "GitOps workflow using Argo CD with Kustomize and GitHub Actions.",
        "stack": ["Argo CD", "Kustomize", "GitHub Actions", "Kubernetes"],
        "tenants": "ApplicationSet for multi-cluster fan out",
        "audit": "Argo CD sync history plus Git commit log",
        "url": "https://github.com/SriLingala/gitops-platform-automation",
    },
    "onprem-k8s-blueprint": {
        "summary": "On-prem Kubernetes blueprint covering RKE2 and k3s edge clusters.",
        "stack": ["RKE2", "k3s", "Terraform", "Helm", "MetalLB", "Argo CD", "Loki"],
        "tenants": "hybrid datacentre + edge fleet",
        "audit": "Terraform plan history, Argo CD sync log, etcd snapshots",
        "url": "https://github.com/SriLingala/onprem-k8s-blueprint",
    },
}

PATTERNS: dict[str, str] = {
    "workload-identity": (
        "Workload Identity binds Kubernetes service accounts to cloud IAM "
        "identities so pods can call cloud APIs without long-lived secrets. "
        "On GKE: annotate the KSA with iam.gke.io/gcp-service-account. "
        "On AKS: federated credentials between AAD app registration and the "
        "OIDC issuer of the cluster. Both platforms map to the same conceptual "
        "model. Secret-less. Auditable. Revokable per workload."
    ),
    "policy-as-code": (
        "Two layers in the banking blueprint. Sentinel runs against Terraform "
        "plans in CI and blocks non-compliant infrastructure pre-merge. OPA "
        "Gatekeeper runs in-cluster as a validating webhook and blocks non "
        "compliant Kubernetes resources at admission time. Belt and braces."
    ),
    "multi-tenant-namespaces": (
        "Each tenant gets a namespace. ResourceQuota and LimitRange set hard "
        "caps. NetworkPolicy default-deny enforced via Gatekeeper. RBAC bound "
        "to a per-tenant Group from the identity provider. Argo CD AppProject "
        "limits which Git paths the tenant can deploy from."
    ),
    "gitops-fleet": (
        "ApplicationSet generates one Argo CD Application per cluster from a "
        "central Git directory. New clusters self-onboard by appearing in the "
        "cluster registry Secret. Drift is detected automatically. Manual "
        "kubectl is forbidden by RBAC except for break-glass accounts."
    ),
}

RUNBOOKS: dict[str, list[str]] = {
    "argocd-out-of-sync": [
        "Confirm the Application is OutOfSync in the Argo CD UI.",
        "Run `argocd app diff <name>` to see the drift.",
        "If the drift is benign (e.g. controller-managed annotations), add "
        "it to the ignoreDifferences block in the Application.",
        "If the drift is real, identify the actor via Cloud Audit Logs / "
        "Kubernetes audit. Revoke access if it was unauthorised.",
        "Run `argocd app sync <name>` to restore Git as the source of truth.",
    ],
    "node-pool-pressure": [
        "Check `kubectl top nodes` for the affected pool.",
        "If CPU/memory pressure, evict pods with low priority and let the "
        "cluster autoscaler grow the pool.",
        "If disk pressure, identify the noisy neighbour with "
        "`kubectl describe node` events. Apply a PodDisruptionBudget cap.",
        "For GPU pools specifically, check MIG slicing config. A GPU may be "
        "fragmented across small workloads that block a larger request.",
    ],
}

COMPLIANCE_CHECKS: dict[str, list[dict[str, str]]] = {
    "namespace": [
        {"check": "ResourceQuota present", "verify": "kubectl get resourcequota -n <ns>"},
        {"check": "LimitRange present", "verify": "kubectl get limitrange -n <ns>"},
        {"check": "NetworkPolicy default-deny", "verify": "kubectl get networkpolicy -n <ns>"},
        {"check": "RBAC scoped to tenant Group", "verify": "kubectl get rolebindings -n <ns>"},
    ],
    "image": [
        {"check": "Signed by trusted signer", "verify": "cosign verify <image>"},
        {"check": "Scanned within last 7 days", "verify": "Aqua / Harbor scan timestamp"},
        {"check": "No critical CVEs", "verify": "Aqua / Harbor report"},
        {"check": "From approved registry", "verify": "image prefix in allowlist"},
    ],
}


# ---- Helpers ---------------------------------------------------------------

def _audit(tool: str, **fields: object) -> str:
    """Log a tool call and return the call id for downstream correlation."""
    call_id = uuid.uuid4().hex[:8]
    log.info("call=%s tool=%s %s", call_id, tool, fields)
    return call_id


# ---- MCP tools -------------------------------------------------------------

@mcp.tool()
def list_blueprints() -> list[dict[str, str]]:
    """List all platform blueprints available in this knowledge base.

    Returns a list of {name, summary, url} entries. Use describe_blueprint to
    pull the full description for any one of them.
    """
    _audit("list_blueprints")
    return [
        {"name": name, "summary": str(data["summary"]), "url": str(data["url"])}
        for name, data in BLUEPRINTS.items()
    ]


@mcp.tool()
def describe_blueprint(name: BlueprintName) -> dict[str, object]:
    """Return the full description for one named blueprint.

    Args:
        name: blueprint name. Use list_blueprints to discover available names.
    """
    _audit("describe_blueprint", name=name)
    if name not in BLUEPRINTS:
        raise ValueError(
            f"Unknown blueprint '{name}'. Available: {', '.join(BLUEPRINTS)}"
        )
    return {"name": name, **BLUEPRINTS[name]}


@mcp.tool()
def describe_pattern(pattern: PatternName) -> dict[str, str]:
    """Explain a platform design pattern in plain prose.

    Args:
        pattern: one of workload-identity, policy-as-code,
                 multi-tenant-namespaces, gitops-fleet.
    """
    _audit("describe_pattern", pattern=pattern)
    if pattern not in PATTERNS:
        raise ValueError(
            f"Unknown pattern '{pattern}'. Available: {', '.join(PATTERNS)}"
        )
    return {"pattern": pattern, "description": PATTERNS[pattern]}


@mcp.tool()
def get_runbook(scenario: RunbookScenario) -> dict[str, object]:
    """Return the runbook steps for a common incident scenario.

    Args:
        scenario: short scenario name. Try argocd-out-of-sync or
                  node-pool-pressure.
    """
    _audit("get_runbook", scenario=scenario)
    if scenario not in RUNBOOKS:
        raise ValueError(
            f"No runbook for '{scenario}'. Available: {', '.join(RUNBOOKS)}"
        )
    return {"scenario": scenario, "steps": RUNBOOKS[scenario]}


@mcp.tool()
def check_compliance(component: ComponentName) -> dict[str, object]:
    """Return the compliance check matrix for a platform component.

    Args:
        component: one of namespace or image.
    """
    _audit("check_compliance", component=component)
    if component not in COMPLIANCE_CHECKS:
        raise ValueError(
            f"No compliance checks for '{component}'. "
            f"Available: {', '.join(COMPLIANCE_CHECKS)}"
        )
    return {"component": component, "checks": COMPLIANCE_CHECKS[component]}


def main() -> None:
    """Entry point used by the `platform-mcp` console script."""
    log.info("starting platform-mcp over stdio")
    mcp.run()


if __name__ == "__main__":
    main()
