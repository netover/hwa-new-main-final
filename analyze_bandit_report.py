import json

# Load the Bandit report
with open("bandit_security_report_new.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print("=== BANDIT SECURITY ANALYSIS REPORT ===")
print(f"Generated: {data.get('generated_at', 'Unknown')}")
print(f"Bandit version: {data.get('bandit_version', 'Unknown')}")
print()

# Count total issues by severity
severity_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
total_files = len(data["results"])
total_issues = 0

# Handle the results structure (list of files)
for file_result in data["results"]:
    filename = file_result.get("filename", "Unknown")
    issues = file_result.get("issues", [])
    total_issues += len(issues)
    for issue in issues:
        severity = issue.get("issue_severity", "UNKNOWN")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

print(f"Files scanned: {total_files}")
print(f"Total security issues found: {total_issues}")
print()
print("Issues by severity:")
for severity, count in severity_counts.items():
    if count > 0:
        print(f"  {severity}: {count}")

print()
print("=== TOP 10 MOST COMMON ISSUES ===")

# Count issues by type
issue_types = {}
for file_result in data["results"]:
    for issue in file_result.get("issues", []):
        test_id = issue.get("test_id", "UNKNOWN")
        issue_types[test_id] = issue_types.get(test_id, 0) + 1

# Sort by frequency
sorted_issues = sorted(issue_types.items(), key=lambda x: x[1], reverse=True)

for test_id, count in sorted_issues[:10]:
    print(f"{test_id}: {count} occurrences")

print()
print("=== DETAILED ISSUES BY FILE (TOP 5) ===")

# Get top 5 files with most issues
file_issue_counts = {}
for file_result in data["results"]:
    filename = file_result.get("filename", "Unknown")
    file_issue_counts[filename] = len(file_result.get("issues", []))

sorted_files = sorted(file_issue_counts.items(), key=lambda x: x[1], reverse=True)

for filename, count in sorted_files[:5]:
    if count > 0:
        print(f"\n{filename}: {count} issues")
        # Find the file result and show first 3 issues
        for file_result in data["results"]:
            if file_result.get("filename") == filename:
                issues = file_result.get("issues", [])[:3]
                for issue in issues:
                    print(
                        f"  - {issue.get('test_name', 'Unknown')} ({issue.get('issue_severity', 'Unknown')})"
                    )
                    print(
                        f"    Line {issue.get('line_number', '?')}: {issue.get('line_range', ['?'])[0] if issue.get('line_range') else '?'}"
                    )
                break
