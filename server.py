"""
platform-mcp

An MCP server that exposes platform engineering knowledge as tools Claude can
call. Demonstrates a working Model Context Protocol implementation built on
the official MCP Python SDK.

Tools exposed:
  - list_blueprints()           returns the four reference platform blueprints
  - describe_pattern(pattern)   returns the design pattern for a given component
  - get_runbook(scenario)       returns a runbook for a common incident scenario
  - check_compliance(component) returns a compliance check matrix for a component

Run:
    pip install mcp anthropic
    python server.py

Or wire into Claude Desktop config:
    {
      "mcpServers": {
        "platform-mcp": {
          "command": "python",
          "args": ["/absolute/path/to/server.py"]
        }
      }
    }
"""
from __future__ import annotations
import json
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("platform-mcp")


# ---- Knowledge base --------------------------------------------------------
# In production you would back this with a real source: Git, Confluence, your
# CMDB, a Postgres table, a vector store, whatever. For the demo it lives in
# Python dictionaries.

BLUEPRINTS: dict[str, dict[str, Any]] = {
    "idp-banking-blueprint": {
        "summary": "Internal Developer Platform reference for regulated banking on GKE.",
        "stack": ["GKE", "Terraform", "Argo CD", "Sentinel", "OPA", "Workload Identity"],
        "tenants": "multi-tenant via namespaces",
        "audit": "full audit trail via Cloud Audit Logs and Argo CD history",
        "url": "https://github.com/SriLingala/idp-banking-blueprint",
    },
    "aks-platform": {
        "summary": "Production-grade AKS blueprint.",
        "stack": ["AKS", "Terraform", "Helm", "Workload Identity", "Key Vault",
                  "Prometheus", "cert-manager", "Ingress NGINX", "GitHub Actions"],
        "tenants": "shared platform add-ons across namespaces",
        "audit": "GitHub Actions CI logs, Azure Activity Logs",
        "url": "https://github.com/SriLingala/aks-platform",
    },
    "ml-platform-k8s": {
        "summary": "AKS-based MLOps platform with GPU node pools.",
        "stack": ["AKS", "GPU node pools", "MLflow", "Argo Workflows",
                  "KServe", "GitOps", "Helm"],
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
}

PATTERNS = {
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

RUNBOOKS = {
    "argocd-out-of-sync": (
        "1. Confirm the Application is OutOfSync in the Argo CD UI. "
        "2. Run `argocd app diff <name>` to see the drift. "
        "3. If the drift is benign (e.g. controller-managed annotations), add "
        "to the ignoreDifferences block in the Application. "
        "4. If the drift is real, identify the actor (Cloud Audit Logs / "
        "Kubernetes audit). Revoke the access if it was unauthorised. "
        "5. Run `argocd app sync <name>` to restore Git as the source of truth."
    ),
    "node-pool-pressure": (
        "1. Check `kubectl top nodes` for the affected pool. "
        "2. If CPU/memory pressure, evict pods with low priority and let the "
        "cluster autoscaler grow the pool. "
        "3. If disk pressure, identify the noisy neighbour with "
        "`kubectl describe node` events. Apply a PodDisruptionBudget cap. "
        "4. For GPU pools specifically, check MIG slicing config. A GPU may be "
        "fragmented across small workloads that block a larger request."
    ),
}

COMPLIANCE_CHECKS = {
    "namespace": [
        ("ResourceQuota present",      "kubectl get resourcequota -n <ns>"),
        ("LimitRange present",         "kubectl get limitrange -n <ns>"),
        ("NetworkPolicy default-deny", "kubectl get networkpolicy -n <ns>"),
        ("RBAC scoped to tenant Group","kubectl get rolebindings -n <ns>"),
    ],
    "image": [
        ("Signed by trusted signer",    "cosign verify <image>"),
        ("Scanned within last 7 days",  "Aqua / Harbor scan timestamp"),
        ("No critical CVEs",            "Aqua / Harbor report"),
        ("From approved registry",      "image prefix in allowlist"),
    ],
}


# ---- MCP tools -------------------------------------------------------------
@mcp.tool()
def list_blueprints() -> str:
    """List all platform blueprints available in this knowledge base."""
    return json.dumps(
        [{"name": name, "summary": data["summary"], "url": data["url"]}
         for name, data in BLUEPRINTS.items()],
        indent=2,
    )


@mcp.tool()
def describe_blueprint(name: str) -> str:
    """Return the full description for one named blueprint.

    Args:
        name: blueprint name. Use list_blueprints to discover available names.
    """
    if name not in BLUEPRINTS:
        return f"Unknown blueprint '{name}'. Available: {', '.join(BLUEPRINTS)}"
    return json.dumps(BLUEPRINTS[name], indent=2)


@mcp.tool()
def describe_pattern(pattern: str) -> str:
    """Explain a platform design pattern in plain prose.

    Args:
        pattern: one of workload-identity, policy-as-code,
                 multi-tenant-namespaces, gitops-fleet.
    """
    if pattern not in PATTERNS:
        return f"Unknown pattern '{pattern}'. Available: {', '.join(PATTERNS)}"
    return PATTERNS[pattern]


@mcp.tool()
def get_runbook(scenario: str) -> str:
    """Return the runbook steps for a common incident scenario.

    Args:
        scenario: short scenario name. Try argocd-out-of-sync or
                  node-pool-pressure.
    """
    if scenario not in RUNBOOKS:
        return f"No runbook for '{scenario}'. Available: {', '.join(RUNBOOKS)}"
    return RUNBOOKS[scenario]


@mcp.tool()
def check_compliance(component: str) -> str:
    """Return the compliance check matrix for a platform component.

    Args:
        component: one of namespace or image.
    """
    if component not in COMPLIANCE_CHECKS:
        return f"No compliance checks for '{component}'. Available: {', '.join(COMPLIANCE_CHECKS)}"
    rows = COMPLIANCE_CHECKS[component]
    return "\n".join(f"- {check}: {how_to_verify}" for check, how_to_verify in rows)


if __name__ == "__main__":
    mcp.run()
