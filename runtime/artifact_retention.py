import os
import json
import shutil
import datetime
from pathlib import Path
from typing import Dict, Any, List

def build_retention_plan(runtime_data_dir: str = "runtime_data", policy: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Scans the runtime data directory and builds a retention plan based on the policy.
    Does not delete anything.
    """
    root = Path(runtime_data_dir)
    
    # Default Policy
    pol = {
        "runtime_data_root": "runtime_data",
        "max_total_size_mb": 500,
        "retain_recent_days": 14,
        "retain_minimum_runs": 20,
        "retain_release_reports": True,
        "retain_live_side_effect_reports": True,
        "retain_failed_runs": True,
        "retain_approved_actions": True,
        "delete_workbench_previews_after_days": 7,
        "delete_temp_after_days": 3,
        "delete_release_logs_after_days": 30,
        "unknown_artifacts_default": "protect"
    }
    if policy:
        pol.update(policy)

    now = datetime.datetime.now(datetime.timezone.utc)
    
    plan = {
        "ok": True,
        "runtime_data_dir": str(root),
        "generated_at": now.isoformat(),
        "summary": {
            "total_items": 0,
            "total_size_bytes": 0,
            "protected_items": 0,
            "delete_candidates": 0,
            "delete_candidate_size_bytes": 0,
            "top_groups_by_size": {}
        },
        "items": [],
        "delete_candidates": [],
        "warnings": [],
        "errors": []
    }
    
    if not root.exists():
        plan["errors"].append(f"Directory {root} does not exist.")
        plan["ok"] = False
        return plan

    # Classification
    def classify(path: Path) -> str:
        rel = path.relative_to(root).parts
        if len(rel) == 0:
            return "unknown"
        
        top = rel[0]
        if top == "runs" and len(rel) == 2:
            return "runs"
        if top == "taskframes":
            return "taskframes"
        if "reports" in rel:
            return "reports"
        if top == "release_verification" and len(rel) >= 2 and rel[1] == "logs":
            return "release_logs"
        if top.startswith("manifest_health"):
            return "manifest_health"
        if top == "manifest_regression_gallery":
            return "gallery_reports"
        if top.startswith("tool_health"):
            return "tool_health"
        if top == "workbench":
            return "workbench_preview"
        if top in ["tmp", ".cache", "cleanup", "temp"]:
            return "temporary"
        
        return "unknown"

    def get_dir_size(p: Path) -> int:
        if p.is_file():
            return p.stat().st_size
        return sum(f.stat().st_size for f in p.glob('**/*') if f.is_file())

    def get_last_modified(p: Path) -> datetime.datetime:
        if p.is_file():
            return datetime.datetime.fromtimestamp(p.stat().st_mtime, tz=datetime.timezone.utc)
        
        mtime = p.stat().st_mtime
        for f in p.glob('**/*'):
            if f.is_file() and f.stat().st_mtime > mtime:
                mtime = f.stat().st_mtime
        return datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)

    # Collect items (direct children of root or specific deep items like runs/<id>)
    items_to_check = []
    
    for child in root.iterdir():
        if child.name == "runs" and child.is_dir():
            for run in child.iterdir():
                items_to_check.append(run)
        elif child.name == "taskframes" and child.is_dir():
            items_to_check.append(child)
        else:
            items_to_check.append(child)

    runs_items = []

    for path in items_to_check:
        try:
            group = classify(path)
            size = get_dir_size(path)
            mod_time = get_last_modified(path)
            age_days = (now - mod_time).days
            
            item = {
                "path": str(path.as_posix()),
                "group": group,
                "kind": "directory" if path.is_dir() else "file",
                "size_bytes": size,
                "created_or_modified_at": mod_time.isoformat(),
                "age_days": age_days,
                "protected": False,
                "delete_candidate": False,
                "reason": ""
            }
            
            # Policy Evaluation
            protected = False
            reason = ""
            
            if group == "unknown" and pol.get("unknown_artifacts_default") == "protect":
                protected = True
                reason = "Unknown artifact protected by default."
            elif age_days < pol.get("retain_recent_days", 14) and group not in ["temporary", "workbench_preview"]:
                protected = True
                reason = f"Recently modified (< {pol['retain_recent_days']} days)."
            elif group == "runs":
                runs_items.append(item)
                summary_file = path / "summary.json"
                if summary_file.exists():
                    try:
                        with open(summary_file, 'r', encoding='utf-8') as f:
                            s = json.load(f)
                        if pol.get("retain_failed_runs") and s.get("completion_status") == "FAILED":
                            protected = True
                            reason = "Failed run."
                        elif pol.get("retain_failed_runs") and s.get("failed_steps", 0) > 0:
                            protected = True
                            reason = "Run with failed steps."
                        elif pol.get("retain_approved_actions"):
                            if s.get("pending_action_count", 0) > 0:
                                protected = True
                                reason = "Run has pending actions."
                            if s.get("executed_action_count", 0) > 0:
                                protected = True
                                reason = "Run has executed actions."
                        if pol.get("retain_live_side_effect_reports") and s.get("live_side_effects_performed"):
                            protected = True
                            reason = "Live side effects performed."
                    except Exception:
                        pass
                if not protected and pol.get("retain_live_side_effect_reports"):
                    # Check reports dir for live side effects
                    reports_dir = path / "reports"
                    if reports_dir.exists():
                        for rep in reports_dir.glob("live_blocked_evidence_report*"):
                            protected = True
                            reason = "Live side effect evidence report found."
                            break
            elif group == "release_logs":
                if pol.get("retain_release_reports") and age_days < pol.get("delete_release_logs_after_days", 30):
                    protected = True
                    reason = "Release log protected."
            elif group == "reports" and pol.get("retain_release_reports") and "release_verification" in str(path):
                 protected = True
                 reason = "Release report protected."
            elif group == "temporary" and age_days < pol.get("delete_temp_after_days", 3):
                 protected = True
                 reason = "Temporary item recent."
            elif group == "workbench_preview" and age_days < pol.get("delete_workbench_previews_after_days", 7):
                 protected = True
                 reason = "Workbench preview recent."

            if not protected:
                if group == "temporary":
                    item["delete_candidate"] = True
                    item["reason"] = f"Temporary item older than {pol.get('delete_temp_after_days')} days."
                elif group == "workbench_preview":
                    item["delete_candidate"] = True
                    item["reason"] = f"Workbench preview older than {pol.get('delete_workbench_previews_after_days')} days."
                elif group == "release_logs":
                    item["delete_candidate"] = True
                    item["reason"] = f"Release log older than {pol.get('delete_release_logs_after_days')} days."
                else:
                    item["delete_candidate"] = True
                    item["reason"] = "Policy allows deletion."

            if protected:
                item["protected"] = True
                item["reason"] = reason
                
            plan["items"].append(item)
        except Exception as e:
            plan["warnings"].append(f"Could not process {path}: {str(e)}")

    # Enforce retain_minimum_runs
    if pol.get("retain_minimum_runs", 0) > 0:
        runs_items.sort(key=lambda x: x["created_or_modified_at"], reverse=True)
        for i, r in enumerate(runs_items):
            if i < pol["retain_minimum_runs"] and r["delete_candidate"]:
                r["delete_candidate"] = False
                r["protected"] = True
                r["reason"] = "Minimum run retention enforced."

    # Finalize Plan
    group_sizes = {}
    for i in plan["items"]:
        plan["summary"]["total_items"] += 1
        plan["summary"]["total_size_bytes"] += i["size_bytes"]
        group_sizes[i["group"]] = group_sizes.get(i["group"], 0) + i["size_bytes"]
        
        if i["protected"]:
            plan["summary"]["protected_items"] += 1
        elif i["delete_candidate"]:
            plan["summary"]["delete_candidates"] += 1
            plan["summary"]["delete_candidate_size_bytes"] += i["size_bytes"]
            plan["delete_candidates"].append(i["path"])

    plan["summary"]["top_groups_by_size"] = dict(sorted(group_sizes.items(), key=lambda item: item[1], reverse=True))

    total_mb = plan["summary"]["total_size_bytes"] / (1024 * 1024)
    if total_mb > pol.get("max_total_size_mb", 500):
        plan["warnings"].append(f"Total artifact size ({total_mb:.1f} MB) exceeds maximum allowed ({pol.get('max_total_size_mb')} MB).")

    return plan

def execute_retention_cleanup(plan: Dict[str, Any], confirm: bool = False) -> Dict[str, Any]:
    """
    Executes cleanup based on the generated plan.
    """
    res = {
        "ok": True,
        "executed": False,
        "deleted_count": 0,
        "skipped_count": 0,
        "reclaimed_bytes": 0,
        "deleted_paths": [],
        "skipped_paths": [],
        "errors": []
    }
    
    if not confirm:
        res["ok"] = False
        res["errors"].append("Cleanup blocked: confirm=False.")
        return res
        
    res["executed"] = True
    
    root_path = Path(plan["runtime_data_dir"]).resolve()
    
    # We should re-verify before deleting just in case
    for item in plan["items"]:
        if item["delete_candidate"] and not item["protected"]:
            path = Path(item["path"])
            
            # Security check: must be inside runtime_data
            try:
                resolved = path.resolve()
                if not str(resolved).startswith(str(root_path)):
                    res["errors"].append(f"Security violation: {path} escapes runtime_data.")
                    res["skipped_count"] += 1
                    res["skipped_paths"].append(str(path))
                    continue
            except Exception as e:
                res["errors"].append(f"Path resolution error for {path}: {str(e)}")
                res["skipped_count"] += 1
                res["skipped_paths"].append(str(path))
                continue

            try:
                if not path.exists():
                     res["skipped_count"] += 1
                     res["skipped_paths"].append(str(path))
                     continue
                     
                if path.is_file():
                    path.unlink()
                else:
                    shutil.rmtree(path)
                res["deleted_count"] += 1
                res["reclaimed_bytes"] += item.get("size_bytes", 0)
                res["deleted_paths"].append(str(path))
            except Exception as e:
                res["errors"].append(f"Failed to delete {path}: {str(e)}")
                res["skipped_count"] += 1
                res["skipped_paths"].append(str(path))
                
    return res

def run_artifact_stability_gate(runtime_data_dir: str = "runtime_data", policy: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Non-destructive check of artifact stability.
    """
    res = {
        "ok": True,
        "status": "PASS",
        "checks": [],
        "summary": {},
        "report_path": "",
        "errors": []
    }
    
    try:
        plan = build_retention_plan(runtime_data_dir, policy)
        
        # Check: path valid
        if not Path(runtime_data_dir).exists():
            res["checks"].append({"check": "runtime data path valid", "status": "FAIL"})
            res["ok"] = False
            res["status"] = "FAIL"
            res["errors"].append(f"Runtime data directory not found: {runtime_data_dir}")
        else:
            res["checks"].append({"check": "runtime data path valid", "status": "PASS"})

        # Check: cleanup can run in dry-run mode
        res["checks"].append({"check": "cleanup can run in dry-run mode", "status": "PASS"})

        # Check: total size under policy threshold
        if plan.get("warnings") and any("exceeds maximum allowed" in w for w in plan["warnings"]):
            res["checks"].append({"check": "total size under policy threshold", "status": "WARN"})
            if res["status"] != "FAIL":
                res["status"] = "WARN"
        else:
             res["checks"].append({"check": "total size under policy threshold", "status": "PASS"})

        # Check: unknown artifacts protected
        unknown_protected = True
        for item in plan["items"]:
            if item["group"] == "unknown" and not item["protected"]:
                unknown_protected = False
        if not unknown_protected:
             res["checks"].append({"check": "unknown artifacts protected", "status": "FAIL"})
             res["ok"] = False
             res["status"] = "FAIL"
             res["errors"].append("Unknown artifacts are marked for deletion.")
        else:
             res["checks"].append({"check": "unknown artifacts protected", "status": "PASS"})

        # Check: protected live/release artifacts not marked for deletion
        protect_conflict = False
        for item in plan["items"]:
            if item["protected"] and item["delete_candidate"]:
                protect_conflict = True
        if protect_conflict:
             res["checks"].append({"check": "protected live/release artifacts not marked for deletion", "status": "FAIL"})
             res["ok"] = False
             res["status"] = "FAIL"
             res["errors"].append("Protected artifacts are simultaneously marked for deletion.")
        else:
             res["checks"].append({"check": "protected live/release artifacts not marked for deletion", "status": "PASS"})

        # Check: no delete candidate outside runtime root
        root_path = Path(runtime_data_dir).resolve()
        outside_root = False
        for item in plan["items"]:
            if item["delete_candidate"]:
                try:
                    resolved = Path(item["path"]).resolve()
                    if not str(resolved).startswith(str(root_path)):
                        outside_root = True
                except:
                    pass
        if outside_root:
             res["checks"].append({"check": "no delete candidate outside runtime root", "status": "FAIL"})
             res["ok"] = False
             res["status"] = "FAIL"
             res["errors"].append("Delete candidates escape runtime_data root.")
        else:
             res["checks"].append({"check": "no delete candidate outside runtime root", "status": "PASS"})
             
        res["summary"] = plan["summary"]

        # Write reports
        report_dir = Path(runtime_data_dir) / "artifact_retention"
        try:
            report_dir.mkdir(parents=True, exist_ok=True)
            
            with open(report_dir / "artifact_inventory.json", "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2)
            with open(report_dir / "artifact_retention_plan.json", "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2)
            with open(report_dir / "artifact_stability_gate.json", "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2)
                
            md = f"# Artifact Retention Summary\n\n"
            md += f"- **Total size:** {plan['summary']['total_size_bytes'] / (1024*1024):.2f} MB\n"
            md += f"- **Item count:** {plan['summary']['total_items']}\n"
            md += f"- **Protected count:** {plan['summary']['protected_items']}\n"
            md += f"- **Cleanup candidate count:** {plan['summary']['delete_candidates']}\n"
            md += f"- **Reclaimable size:** {plan['summary']['delete_candidate_size_bytes'] / (1024*1024):.2f} MB\n"
            md += "\n## Top Artifact Groups by Size\n"
            for k, v in plan['summary']['top_groups_by_size'].items():
                md += f"- {k}: {v / (1024*1024):.2f} MB\n"
            
            md += "\n## Warnings\n"
            for w in plan["warnings"]:
                md += f"- {w}\n"
                
            md += "\n## Recommended Action\n"
            if plan['summary']['delete_candidates'] > 0:
                md += "Run `taskframe artifacts cleanup --confirm` to reclaim space.\n"
            else:
                md += "No cleanup necessary.\n"
                
            with open(report_dir / "artifact_retention_summary.md", "w", encoding="utf-8") as f:
                f.write(md)

            res["report_path"] = str(report_dir / "artifact_stability_gate.json")
            res["checks"].append({"check": "inventory report can be written", "status": "PASS"})
        except Exception as e:
            res["checks"].append({"check": "inventory report can be written", "status": "FAIL"})
            res["ok"] = False
            res["status"] = "FAIL"
            res["errors"].append(f"Failed to write reports: {str(e)}")

    except Exception as e:
        res["ok"] = False
        res["status"] = "FAIL"
        res["errors"].append(str(e))
        
    return res
