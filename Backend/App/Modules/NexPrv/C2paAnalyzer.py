"""NEX-PRV Provenance Intelligence: C2PA content credentials of the preserved original (archive §4, module 08).

Outcomes are kept distinct, because they mean different things:
  ABSENT        no manifest is embedded. Most media has none; absence says nothing about authenticity.
  VALID         the manifest's signature and hashes verify. The signer is reported; with no trust list
                configured the signer is UNTRUSTED (unknown), not "fake". A valid credential is evidence of
                signed assertions about the file's history, not proof that its content is true.
  INVALID       verification failed (e.g. a hash mismatch: the content changed after it was signed).
  UNSUPPORTED   the SDK cannot read this format (the planner already skips formats outside the confirmed list).
Remote manifests are reported by URL only; NEXTRON does not fetch them (no outbound requests from analysis).
"""

from pathlib import Path

import c2pa

from Backend.App.Contracts.ExecutionStates import ExecutionState
from Backend.App.Contracts.Findings import Assertion, Finding
from Backend.App.Modules.Engine import EngineOutput

VERSION = "nextron-prv/1"
MODULE = "NEX-PRV"
PARAMETERS = {"trust_list": "none configured", "fetch_remote_manifests": False}

# codes the SDK reports that concern the signer's identity rather than the file's integrity
_TRUST_CODES = {"signingCredential.untrusted", "signingCredential.ocsp.skipped", "signingCredential.ocsp.inaccessible"}


def _actions(manifest: dict) -> list[dict]:
    found = []
    for a in manifest.get("assertions", []) or []:
        if str(a.get("label", "")).startswith("c2pa.actions"):
            for act in (a.get("data") or {}).get("actions", []) or []:
                found.append({k: act.get(k) for k in ("action", "when", "softwareAgent", "digitalSourceType") if act.get(k) is not None})
    return found


def analyze(path: Path, evidence_id, *, mime_type: str, settings=None) -> EngineOutput:
    tools = {"c2pa-python": getattr(c2pa, "__version__", None) or "0.39", "c2pa-rs": c2pa.sdk_version()}
    ev = [evidence_id]
    out = EngineOutput(ExecutionState.COMPLETED, tool_versions=tools)

    def finding(kind, title, description, measurement, limitations=()):
        out.findings.append(Finding(module_id=MODULE, evidence_ids=ev, assertion=Assertion.OBSERVATION, finding_type=kind, title=title,
                                    description=description, measurement=measurement, limitations=list(limitations), parameters=PARAMETERS))

    try:
        with open(path, "rb") as f:  # the SDK reads from the stream; the file is never loaded whole
            reader = c2pa.Reader(mime_type, f)
            try:
                state = reader.get_validation_state()  # "Trusted" | "Valid" | "Invalid"
                results = reader.get_validation_results() or {}
                active = reader.get_active_manifest() or {}
                remote = reader.get_remote_url()
                embedded = reader.is_embedded()
            finally:
                reader.close()
    except c2pa.C2paError.ManifestNotFound:
        finding("NO_CONTENT_CREDENTIALS", "No content credentials", "No C2PA manifest is embedded in this file.",
                {"state": "ABSENT"}, ["Most cameras, apps and platforms do not add credentials, and many strip them; absence is not evidence of manipulation"])
        return out
    except c2pa.C2paError.NotSupported as exc:
        return EngineOutput(ExecutionState.SKIPPED, "NOT_APPLICABLE", f"The C2PA SDK cannot read this format ({mime_type}): {exc}", tool_versions=tools)
    except c2pa.C2paError as exc:
        finding("CONTENT_CREDENTIALS_UNREADABLE", "Content credentials present but unreadable",
                f"The SDK reported: {str(exc)[:300]}", {"state": "INVALID", "error": str(exc)[:500]})
        return out

    status = (results.get("activeManifest") or {})
    failures = status.get("failure", []) or []
    integrity_failures = [f for f in failures if f.get("code") not in _TRUST_CODES]
    trust_failures = [f for f in failures if f.get("code") in _TRUST_CODES]
    signature = active.get("signature_info") or {}
    generators = [g.get("name") for g in active.get("claim_generator_info", []) or [] if g.get("name")]
    outcome = "INVALID" if (state == "Invalid" or integrity_failures) else "TRUSTED" if state == "Trusted" else "VALID"
    measurement = {
        "state": outcome, "sdk_validation_state": state, "signer": signature.get("common_name"), "issuer": signature.get("issuer"),
        "algorithm": signature.get("alg"), "signed_at": signature.get("time"), "claim_generator": generators, "title": active.get("title"),
        "actions": _actions(active), "ingredients": len(active.get("ingredients", []) or []), "embedded": embedded, "remote_manifest_url": remote,
        "failures": [{"code": f.get("code"), "explanation": f.get("explanation")} for f in failures],
        "successes": [f.get("code") for f in status.get("success", []) or []],
    }
    signer = measurement["signer"] or "an unnamed signer"
    if outcome == "INVALID":
        finding("CONTENT_CREDENTIALS_INVALID", "Content credentials fail verification",
                "The manifest does not verify against this file: " + "; ".join(f"{f.get('code')} ({f.get('explanation')})" for f in integrity_failures)[:900],
                measurement, ["A failed hash check means the bytes differ from what was signed; it does not say what changed or who changed it"])
    else:
        trusted = outcome == "TRUSTED"
        finding("CONTENT_CREDENTIALS_VALID", f"Content credentials signed by {signer}" + ("" if trusted else " (signer not on a trust list)"),
                "The signature and content hashes verify." + ("" if trusted else " No trust list is configured, so the signer's identity is not vouched for."),
                measurement, ["Credentials record claims made by the signer about the file's history; they do not prove the content is true",
                              *([] if trusted else ["Signer identity is unverified: " + ", ".join(f.get("code") for f in trust_failures)])])
    if remote:
        out.limitations.append(f"A remote manifest is referenced ({remote}); NEXTRON does not fetch it")
    return out
