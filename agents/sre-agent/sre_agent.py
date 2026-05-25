#!/usr/bin/env python3
"""
SRE Agent - Unified Incident Response + ChatOps
Monitors EKS cluster health, auto-remediates issues, and accepts commands via chat.
"""

import json
import subprocess
import sys
import re
from datetime import datetime, timezone


def run_cmd(cmd: str, timeout: int = 30) -> tuple[int, str]:
    """Run shell command and return (returncode, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return 1, "Command timed out"
    except Exception as e:
        return 1, str(e)


def kubectl(cmd: str, timeout: int = 30) -> tuple[int, str]:
    """Run kubectl command."""
    return run_cmd(f"kubectl {cmd}", timeout)


# ============================================================
# INCIDENT RESPONSE (Proactive Scan)
# ============================================================

def scan_cluster_health() -> dict:
    """Full cluster health scan."""
    findings = []
    
    # 1. Node health
    rc, out = kubectl("get nodes -o json")
    if rc == 0:
        nodes = json.loads(out)
        for node in nodes.get("items", []):
            name = node["metadata"]["name"]
            conditions = {c["type"]: c["status"] for c in node["status"].get("conditions", [])}
            if conditions.get("Ready") != "True":
                findings.append({
                    "severity": "critical",
                    "type": "node_not_ready",
                    "resource": name,
                    "message": f"Node {name} is NOT Ready",
                    "auto_remediate": False
                })
            # Check resource pressure
            for pressure in ["MemoryPressure", "DiskPressure", "PIDPressure"]:
                if conditions.get(pressure) == "True":
                    findings.append({
                        "severity": "high",
                        "type": "node_pressure",
                        "resource": name,
                        "message": f"Node {name} has {pressure}",
                        "auto_remediate": False
                    })
    
    # 2. Pod health (all namespaces)
    rc, out = kubectl("get pods -A -o json")
    if rc == 0:
        pods = json.loads(out)
        for pod in pods.get("items", []):
            ns = pod["metadata"]["namespace"]
            name = pod["metadata"]["name"]
            phase = pod["status"].get("phase", "Unknown")
            
            # Skip system pods in kube-system that are expected
            if ns == "kube-system" and phase == "Running":
                continue
            
            # CrashLoopBackOff / Error
            for cs in pod["status"].get("containerStatuses", []):
                restart_count = cs.get("restartCount", 0)
                waiting = cs.get("state", {}).get("waiting", {})
                reason = waiting.get("reason", "")
                
                if reason == "CrashLoopBackOff":
                    findings.append({
                        "severity": "critical",
                        "type": "crash_loop",
                        "resource": f"{ns}/{name}",
                        "message": f"Pod {name} in {ns} is CrashLoopBackOff (restarts: {restart_count})",
                        "auto_remediate": True,
                        "action": "restart_pod",
                        "restart_count": restart_count
                    })
                elif reason in ("ImagePullBackOff", "ErrImagePull"):
                    findings.append({
                        "severity": "high",
                        "type": "image_pull_error",
                        "resource": f"{ns}/{name}",
                        "message": f"Pod {name} in {ns}: {reason}",
                        "auto_remediate": False
                    })
                elif restart_count > 5:
                    findings.append({
                        "severity": "warning",
                        "type": "high_restarts",
                        "resource": f"{ns}/{name}",
                        "message": f"Pod {name} in {ns} has {restart_count} restarts",
                        "auto_remediate": False
                    })
            
            # Pending pods
            if phase == "Pending":
                age_str = pod["metadata"].get("creationTimestamp", "")
                if age_str:
                    created = datetime.fromisoformat(age_str.replace("Z", "+00:00"))
                    age_min = (datetime.now(timezone.utc) - created).total_seconds() / 60
                    if age_min > 5:
                        findings.append({
                            "severity": "high",
                            "type": "pod_pending",
                            "resource": f"{ns}/{name}",
                            "message": f"Pod {name} in {ns} pending for {int(age_min)}min",
                            "auto_remediate": False
                        })
    
    # 3. Deployment health
    rc, out = kubectl("get deployments -A -o json")
    if rc == 0:
        deployments = json.loads(out)
        for dep in deployments.get("items", []):
            ns = dep["metadata"]["namespace"]
            name = dep["metadata"]["name"]
            desired = dep["spec"].get("replicas", 0)
            available = dep["status"].get("availableReplicas", 0) or 0
            
            if available < desired:
                findings.append({
                    "severity": "high",
                    "type": "deployment_degraded",
                    "resource": f"{ns}/{name}",
                    "message": f"Deployment {name} in {ns}: {available}/{desired} replicas available",
                    "auto_remediate": False
                })
    
    # 4. Service endpoints
    rc, out = kubectl("get endpoints -n microservices -o json 2>/dev/null")
    if rc == 0:
        try:
            endpoints = json.loads(out)
            for ep in endpoints.get("items", []):
                name = ep["metadata"]["name"]
                subsets = ep.get("subsets", [])
                if not subsets or not any(s.get("addresses") for s in subsets):
                    findings.append({
                        "severity": "critical",
                        "type": "no_endpoints",
                        "resource": f"microservices/{name}",
                        "message": f"Service {name} has no healthy endpoints",
                        "auto_remediate": False
                    })
        except json.JSONDecodeError:
            pass
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
        "total": len(findings),
        "critical": len([f for f in findings if f["severity"] == "critical"]),
        "high": len([f for f in findings if f["severity"] == "high"]),
        "warning": len([f for f in findings if f["severity"] == "warning"]),
    }


def auto_remediate(findings: list) -> list:
    """Auto-remediate findings where possible."""
    actions_taken = []
    
    for f in findings:
        if not f.get("auto_remediate"):
            continue
        
        if f["action"] == "restart_pod":
            ns, pod = f["resource"].split("/")
            # Only auto-restart if < 10 restarts (avoid infinite loop)
            if f.get("restart_count", 0) < 10:
                rc, out = kubectl(f"delete pod {pod} -n {ns}")
                actions_taken.append({
                    "finding": f["message"],
                    "action": f"Deleted pod {pod} in {ns} (will be recreated by deployment)",
                    "success": rc == 0,
                    "output": out
                })
    
    return actions_taken


# ============================================================
# CHATOPS (Reactive Commands)
# ============================================================

COMMANDS = {
    "status": "Show cluster/service status",
    "pods": "List pods (optional: namespace)",
    "logs": "Get pod logs (service name, optional: lines)",
    "restart": "Restart a deployment",
    "scale": "Scale a deployment",
    "health": "Full health scan",
    "top": "Resource usage (nodes/pods)",
    "events": "Recent cluster events",
    "rollback": "Rollback a deployment",
    "help": "Show available commands",
}


def handle_command(command: str) -> str:
    """Parse and execute a ChatOps command."""
    parts = command.strip().lower().split()
    if not parts:
        return format_help()
    
    cmd = parts[0]
    args = parts[1:]
    
    if cmd == "help":
        return format_help()
    elif cmd == "status":
        return cmd_status(args)
    elif cmd == "pods":
        return cmd_pods(args)
    elif cmd == "logs":
        return cmd_logs(args)
    elif cmd == "restart":
        return cmd_restart(args)
    elif cmd == "scale":
        return cmd_scale(args)
    elif cmd == "health":
        return cmd_health()
    elif cmd == "top":
        return cmd_top(args)
    elif cmd == "events":
        return cmd_events(args)
    elif cmd == "rollback":
        return cmd_rollback(args)
    else:
        return f"❓ Unknown command: `{cmd}`\n\nType `help` for available commands."


def format_help() -> str:
    lines = ["🤖 **SRE Agent Commands:**\n"]
    for cmd, desc in COMMANDS.items():
        lines.append(f"• `{cmd}` — {desc}")
    lines.append("\n**Examples:**")
    lines.append("• `status` — cluster overview")
    lines.append("• `pods microservices` — pods in namespace")
    lines.append("• `logs backend-service 50` — last 50 lines")
    lines.append("• `restart backend-service` — rolling restart")
    lines.append("• `scale frontend 3` — scale to 3 replicas")
    return "\n".join(lines)


def cmd_status(args: list) -> str:
    """Cluster status overview."""
    lines = ["📊 Cluster Status\n"]
    
    # Nodes
    rc, out = kubectl("get nodes --no-headers")
    if rc == 0:
        node_lines = [l for l in out.split("\n") if l.strip()]
        ready = sum(1 for l in node_lines if "Ready" in l and "NotReady" not in l)
        check = "✅" if ready == len(node_lines) else "⚠️"
        lines.append(f"🖥 Nodes: {ready}/{len(node_lines)} {check}")
    
    # Pods summary
    rc, out = kubectl("get pods -A --no-headers")
    if rc == 0:
        pod_lines = [l for l in out.split("\n") if l.strip()]
        running = sum(1 for l in pod_lines if "Running" in l)
        check = "✅" if running == len(pod_lines) else "⚠️"
        lines.append(f"📦 Pods: {running}/{len(pod_lines)} {check}")
    
    # Deployments in microservices
    rc, out = kubectl("get deployments -n microservices --no-headers")
    if rc == 0:
        dep_lines = [l for l in out.split("\n") if l.strip()]
        lines.append(f"\n⚙️ Services:")
        for dep in dep_lines:
            parts = dep.split()
            if len(parts) >= 4:
                name, ready_str = parts[0], parts[1]
                r_cur, r_total = ready_str.split("/")
                emoji = "🟢" if r_cur == r_total else "🔴"
                lines.append(f"  {emoji} {name:<18} {ready_str}")
    
    return "\n".join(lines)


def cmd_pods(args: list) -> str:
    """List pods."""
    ns = args[0] if args else "microservices"
    rc, out = kubectl(f"get pods -n {ns} -o wide --no-headers")
    if rc != 0:
        return f"❌ Error: {out}"
    
    lines = [f"📦 Pods in {ns}:\n"]
    for line in out.split("\n"):
        if line.strip():
            parts = line.split()
            if len(parts) >= 5:
                name, ready, status, restarts = parts[0], parts[1], parts[2], parts[3]
                emoji = "🟢" if status == "Running" else "🔴"
                lines.append(f"  {emoji} {name}")
                lines.append(f"     {status} • {ready} ready • {restarts} restarts")
    
    return "\n".join(lines)


def cmd_logs(args: list) -> str:
    """Get logs for a service."""
    if not args:
        return "❌ Usage: `logs <service-name> [lines]`"
    
    service = args[0]
    tail = args[1] if len(args) > 1 else "20"
    
    rc, out = kubectl(f"logs deployment/{service} -n microservices --tail={tail}")
    if rc != 0:
        return f"❌ Error getting logs: {out}"
    
    # Truncate if too long
    if len(out) > 3000:
        out = out[-3000:]
        out = "...(truncated)\n" + out
    
    return f"📋 **Logs: {service}** (last {tail} lines):\n```\n{out}\n```"


def cmd_restart(args: list) -> str:
    """Rolling restart a deployment."""
    if not args:
        return "❌ Usage: `restart <deployment-name>`"
    
    name = args[0]
    rc, out = kubectl(f"rollout restart deployment/{name} -n microservices")
    if rc != 0:
        return f"❌ Error: {out}"
    
    return f"🔄 Restarting deployment `{name}`...\n{out}"


def cmd_scale(args: list) -> str:
    """Scale a deployment."""
    if len(args) < 2:
        return "❌ Usage: `scale <deployment-name> <replicas>`"
    
    name, replicas = args[0], args[1]
    if not replicas.isdigit():
        return "❌ Replicas must be a number"
    
    rc, out = kubectl(f"scale deployment/{name} -n microservices --replicas={replicas}")
    if rc != 0:
        return f"❌ Error: {out}"
    
    return f"⚡ Scaled `{name}` to {replicas} replicas"


def cmd_health() -> str:
    """Full health scan."""
    result = scan_cluster_health()
    
    if result["total"] == 0:
        return "✅ **Cluster Health: All Clear**\n\nNo issues detected. All systems operational."
    
    lines = [f"⚠️ **Cluster Health: {result['total']} issue(s) found**\n"]
    lines.append(f"🔴 Critical: {result['critical']} | 🟠 High: {result['high']} | 🟡 Warning: {result['warning']}\n")
    
    for f in result["findings"]:
        severity_emoji = {"critical": "🔴", "high": "🟠", "warning": "🟡"}[f["severity"]]
        lines.append(f"{severity_emoji} [{f['type']}] {f['message']}")
    
    return "\n".join(lines)


def cmd_top(args: list) -> str:
    """Resource usage."""
    target = args[0] if args else "nodes"
    
    if target == "nodes":
        rc, out = kubectl("top nodes")
    elif target == "pods":
        rc, out = kubectl("top pods -n microservices")
    else:
        return "❌ Usage: `top nodes` or `top pods`"
    
    if rc != 0:
        return f"❌ Error: {out}\n\n(Metrics server may not be installed)"
    
    return f"📈 **Resource Usage ({target}):**\n```\n{out}\n```"


def cmd_events(args: list) -> str:
    """Recent events."""
    ns = args[0] if args else "microservices"
    rc, out = kubectl(f"get events -n {ns} --sort-by='.lastTimestamp' --no-headers | tail -15")
    if rc != 0:
        return f"❌ Error: {out}"
    
    if not out.strip():
        return f"📭 No recent events in `{ns}`"
    
    return f"📋 **Recent Events ({ns}):**\n```\n{out}\n```"


def cmd_rollback(args: list) -> str:
    """Rollback a deployment."""
    if not args:
        return "❌ Usage: `rollback <deployment-name>`"
    
    name = args[0]
    rc, out = kubectl(f"rollout undo deployment/{name} -n microservices")
    if rc != 0:
        return f"❌ Error: {out}"
    
    return f"⏪ Rolled back `{name}` to previous revision\n{out}"


# ============================================================
# MAIN
# ============================================================

def generate_scan_report() -> str:
    """Generate full scan report with auto-remediation."""
    result = scan_cluster_health()
    
    if result["total"] == 0:
        return "✅ **SRE Agent Scan — All Clear**\n\nCluster healthy. No issues detected."
    
    # Auto-remediate
    actions = auto_remediate(result["findings"])
    
    lines = [f"🚨 **SRE Agent Scan — {result['total']} issue(s)**"]
    lines.append(f"⏰ {result['timestamp']}\n")
    lines.append(f"🔴 Critical: {result['critical']} | 🟠 High: {result['high']} | 🟡 Warning: {result['warning']}\n")
    
    lines.append("**Findings:**")
    for f in result["findings"]:
        severity_emoji = {"critical": "🔴", "high": "🟠", "warning": "🟡"}[f["severity"]]
        lines.append(f"{severity_emoji} {f['message']}")
    
    if actions:
        lines.append("\n**Auto-remediation actions:**")
        for a in actions:
            status = "✅" if a["success"] else "❌"
            lines.append(f"{status} {a['action']}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # ChatOps mode: handle command
        command = " ".join(sys.argv[1:])
        print(handle_command(command))
    else:
        # Scan mode: proactive health check
        print(generate_scan_report())
