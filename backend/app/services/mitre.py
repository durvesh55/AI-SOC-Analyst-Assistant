"""Rule-based MITRE ATT&CK suggestions.

IMPORTANT: this is a transparent keyword/category matcher, NOT machine learning and NOT proof of
attacker behaviour. Every result is labelled a *suggestion* that an analyst must validate.
Technique IDs/names/tactics follow MITRE ATT&CK Enterprise (https://attack.mitre.org).
"""
import re

DISCLAIMER = "Suggestion only - based on simple rules; must be validated by an analyst."

# id, name, tactic, matching alert categories, keywords, why-it-relates explanation
RULES = [
    ("T1110", "Brute Force", "Credential Access", ["Brute Force"],
     ["brute force", "failed login", "failed logins", "password spray", "credential stuffing",
      "authentication failure", "multiple failed"],
     "Repeated failed authentication attempts are the typical footprint of password guessing."),
    ("T1078", "Valid Accounts", "Initial Access", ["Suspicious Login"],
     ["impossible travel", "unusual login", "off-hours login", "compromised account",
      "new country", "login from new", "stolen credentials"],
     "Legitimate credentials used in an unusual way may indicate an adversary using a valid account."),
    ("T1566", "Phishing", "Initial Access", ["Phishing"],
     ["phishing", "spearphishing", "malicious attachment", "suspicious email",
      "credential harvesting", "fake login page", "malicious link"],
     "Deceptive emails or links used to gain access or harvest credentials."),
    ("T1204", "User Execution", "Execution", [],
     ["user opened", "macro enabled", "malicious document", "opened attachment",
      "downloaded executable", "double-clicked"],
     "A user running a malicious file or document is a common execution path."),
    ("T1059.001", "Command and Scripting Interpreter: PowerShell", "Execution", [],
     ["powershell", "encodedcommand", "-enc", "invoke-expression", "iex"],
     "Obfuscated or unusual PowerShell activity is often used to run attacker code."),
    ("T1071", "Application Layer Protocol", "Command and Control", [],
     ["beacon", "beaconing", "c2", "command and control", "periodic callback", "callback"],
     "Regular outbound check-ins to an external host are characteristic of C2 communication."),
    ("T1486", "Data Encrypted for Impact", "Impact", [],
     ["ransomware", "files encrypted", "ransom note", ".locked", "mass file rename"],
     "Mass file encryption and ransom notes point to ransomware activity."),
    ("T1048", "Exfiltration Over Alternative Protocol", "Exfiltration", ["Data Exfiltration"],
     ["exfiltration", "large outbound", "unusual outbound", "data transfer", "upload to external"],
     "Large or unusual outbound transfers can indicate data leaving the network."),
    ("T1567", "Exfiltration Over Web Service", "Exfiltration", [],
     ["dropbox", "mega.nz", "pastebin", "cloud storage upload", "google drive upload"],
     "Data uploaded to public web/cloud services may be exfiltration."),
    ("T1046", "Network Service Discovery", "Discovery", ["Network Intrusion"],
     ["port scan", "nmap", "network scan", "service discovery", "host sweep"],
     "Scanning many ports/hosts is typical reconnaissance of internal services."),
    ("T1190", "Exploit Public-Facing Application", "Initial Access", ["Web Attack"],
     ["sql injection", "sqli", "remote code execution", "rce", "path traversal", "cve-", "exploit"],
     "Attacks against internet-facing web applications aim to gain an initial foothold."),
    ("T1505.003", "Server Software Component: Web Shell", "Persistence", [],
     ["web shell", "webshell", "cmd.php", "china chopper"],
     "A web shell gives an attacker persistent remote access through a web server."),
    ("T1068", "Exploitation for Privilege Escalation", "Privilege Escalation", ["Privilege Escalation"],
     ["privilege escalation", "local exploit", "kernel exploit"],
     "Exploiting a flaw to gain higher privileges than the account should have."),
    ("T1548", "Abuse Elevation Control Mechanism", "Privilege Escalation", [],
     ["uac bypass", "sudo abuse", "setuid"],
     "Bypassing or abusing built-in elevation controls to run with higher rights."),
    ("T1003", "OS Credential Dumping", "Credential Access", [],
     ["mimikatz", "lsass", "credential dump", "procdump", "ntds.dit", "sam database"],
     "Reading credential material from the OS (e.g. LSASS memory) is a known attacker technique."),
    ("T1021", "Remote Services", "Lateral Movement", [],
     ["lateral movement", "rdp", "smb", "psexec", "winrm", "remote desktop"],
     "Remote service logins between internal hosts can indicate movement across the network."),
    ("T1053", "Scheduled Task/Job", "Persistence", [],
     ["scheduled task", "schtasks", "cron job", "new service installed"],
     "Scheduled tasks/jobs are a common way to maintain persistence or execute code."),
    ("T1547", "Boot or Logon Autostart Execution", "Persistence", [],
     ["run key", "registry run", "startup folder"],
     "Programs added to autostart locations survive reboots."),
    ("T1070", "Indicator Removal", "Defense Evasion", [],
     ["log cleared", "clear logs", "wevtutil", "event log cleared", "history deleted"],
     "Deleting logs or history hides evidence of attacker activity."),
    ("T1562", "Impair Defenses", "Defense Evasion", [],
     ["antivirus disabled", "defender disabled", "security tool stopped", "tamper protection"],
     "Disabling security tooling lets an adversary operate unseen."),
    ("T1498", "Network Denial of Service", "Impact", ["Denial of Service"],
     ["ddos", "syn flood", "traffic spike", "denial of service", "flood"],
     "Overwhelming a service with traffic to make it unavailable."),
]


def _contains(text: str, term: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None


def suggest_techniques(alert: dict, limit: int = 5) -> list[dict]:
    """Return ranked ATT&CK suggestions for an alert-like dict (title, description, category...)."""
    parts = [alert.get("title", ""), alert.get("description", ""), alert.get("hostname") or ""]
    parts += list(alert.get("indicators") or [])
    text = " ".join(parts).lower()
    category = alert.get("category")

    results = []
    for tid, name, tactic, categories, keywords, why in RULES:
        matched = [k for k in keywords if _contains(text, k)]
        cat_hit = category in categories
        signals = len(matched) + (1 if cat_hit else 0)
        if signals == 0:
            continue
        basis = []
        if cat_hit:
            basis.append(f"alert category is '{category}'")
        if matched:
            basis.append("text contains: " + ", ".join(f"'{m}'" for m in matched))
        results.append(
            {
                "technique_id": tid,
                "technique_name": name,
                "tactic": tactic,
                "confidence": "Medium" if signals >= 2 else "Low",
                "matched_terms": matched,
                "reason": f"Suggested because {' and '.join(basis)}. {why}",
                "status": "Suggested",
                "disclaimer": DISCLAIMER,
                "_signals": signals,
            }
        )
    results.sort(key=lambda r: (-r["_signals"], r["technique_id"]))
    for r in results:
        r.pop("_signals")
    return results[:limit]


def technique_catalog() -> list[dict]:
    return [
        {"technique_id": t, "technique_name": n, "tactic": tac, "categories": cats, "keywords": kws}
        for t, n, tac, cats, kws, _ in RULES
    ]
