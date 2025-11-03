# Resync Use Cases

## 1. Job Status Inquiry

### Description
Operator queries the status of a specific job

### Scenario
Operator needs to know if a critical job completed successfully

### Steps
1. Operator asks: "What is the status of job FINANCE_PAYROLL?"
2. System queries TWS API for real-time status
3. System checks knowledge graph for related information
4. System returns consolidated response with:
   - Current job status
   - Relevant error resolution procedures
   - Contact information for responsible team

### Example Response
```json
{
  "job": "FINANCE_PAYROLL",
  "status": "Completed",
  "start_time": "2025-09-24T08:00:00Z",
  "end_time": "2025-09-24T08:15:00Z",
  "details": {
    "controller": "CTRL_FIN",
    "workstation": "FIN_WS"
  },
  "related_info": {
    "last_failure": null,
    "owner": "finance-team@company.com",
    "documentation": "https://internal-docs/finance-payroll"
  }
}
```

## 2. Failed Jobs Report

### Description
Operator requests list of failed jobs in the last 4 hours

### Scenario
Operator needs to identify and resolve recent job failures

### Steps
1. Operator asks: "Show me failed jobs in the last 4 hours"
2. System queries TWS API for failed jobs in specified time window
3. System adds contextual information from knowledge graph
4. System returns list of failed jobs with resolution guidance

### Example Response
```json
[
  {
    "job": "INVOICE_PROCESSING",
    "status": "Failed",
    "end_time": "2025-09-24T10:30:00Z",
    "error_code": "ABEND_UFL",
    "resolution_steps": [
      "Check input file path",
      "Verify database connection",
      "Consult https://internal-docs/invoice-processing-errors"
    ],
    "owner": "systems-team@company.com"
  }
]
```

## 3. System Health Check

### Description
Operator requests overall system health status

### Scenario
Operator needs quick overview of system status

### Steps
1. Operator asks: "What's the system health?"
2. System queries TWS API for workstations and job statuses
3. System aggregates information into health summary
4. System returns consolidated health report

### Example Response
```json
{
  "timestamp": "2025-09-24T15:30:00Z",
  "workstations": {
    "total": 15,
    "available": 12,
    "unreachable": 3
  },
  "jobs": {
    "total": 245,
    "running": 45,
    "completed": 190,
    "failed": 10
  },
  "critical_path": {
    "on_track": true,
    "delayed_jobs": 2
  }
}
```

## 4. Knowledge Graph Update

### Description
System automatically updates knowledge graph with new resolution pattern

### Scenario
Repeated resolution of similar issues by operators

### Steps
1. IA Auditor detects pattern in resolved issues
2. System creates new knowledge entry with:
   - Problem description
   - Resolution steps
   - Relevant contacts
3. New knowledge becomes available for future queries

### Example Knowledge Entry
```json
{
  "problem": "Input file not found",
  "resolution_steps": [
    "Verify file path in job definition",
    "Check file permissions",
    " Consult https://internal-docs/file-issues"
  ],
  "owner": "operations-team@company.com",
  "created': "2025-09-24T14:00:00Z"
}
```

## 5. Agent Monitoring

### Description
Operator queries status of all agents

### Scenario
Operator needs to verify system components are running

### Steps
1. Operator asks: "Show me all agents"
2. System returns configuration and status of all agents
3. Includes health check results and version information

### Example Response
```json
[
  {
    "name": "TWS Monitor Agent",
    "version": "1.2.0",
    "status": "healthy",
    "last_check": "2025-09-24T15:28:00Z"
  },
  {
    "name": "RAG Knowledge Agent",
    "version": "1.1.3",
    "status": "healthy",
    "last_check": "2025-09-24T15:27:55Z"
  }
]
```

## 6. Agent Interaction

### Description
Operator directly interacts with specific agent

### Scenario
Operator needs detailed information from specific agent

### Steps
1. Operator asks: "Can you show me more about the security agent?"
2. System routes request to specific agent
3. Agent provides detailed information or performs requested action

### Example Interaction
```bash
User: "-talkto security-agent"
Security Agent: "I'm the security audit agent. I can help with security scans, vulnerability checks, and compliance reports."

User: "run security scan"
Security Agent: "Starting security scan...
1. Scanning dependencies...
2. Checking configurations...
3. Validating permissions...
Scan complete. No critical vulnerabilities found. Report available at /reports/security-audit-report.md"
```

## 7. Real-time Monitoring

### Description
Operator requests live updates on system status

### Scenario
Operator needs to monitor critical job execution

### Steps
1. Operator asks: "Monitor job CRITICAL_JOB"
2. System establishes WebSocket connection
3. System sends real-time updates as job progresses

### Example WebSocket Messages
```json
# Initial status
{
  "job": "CRITICAL_JOB",
  "status": "queued"
}

# Progress updates
{
  "job": "CRITICAL_JOB",
  "status": "running",
  "progress": "50%"
}

# Completion
{
  "job": "CRITICAL_JOB",
  "status": "completed",
  "duration": "12s"
}



