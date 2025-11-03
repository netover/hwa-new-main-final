# Contributing to Resync

Thank you for your interest in contributing to Resync! This document outlines our guidelines for participating in the project, whether through code, documentation, or other contributions.

## 📁 Getting Started

1. **Fork the Repository**
   - Click the "Fork" button on the top-right corner of the GitHub repository.
   - This creates a copy of the repository in your account.

2. **Clone Your Fork**
   ```bash
   git clone https://github.com/your-username/hwa-new-1.git
   cd hwa-new-1
   ```

3. **Set Up the Base Branch**
   ```bash
   git remote add upstream https://github.com/netover/hwa-new-1.git
   git fetch upstream
   git checkout main
   git pull upstream main
   ```

## 🧱 Coding Standards

### General Principles
- Follow PEP 8 guidelines
- Keep functions/methods under 30 lines
- Use meaningful variable and function names
- Prefer type hints
- Avoid side effects in functions

### Resync Specific
- **Agent Design**: New agents should follow the pattern in `resync/core/agent_manager.py`
- **API Endpoints**: New endpoints should:
  - Be added to `resync/api/endpoints.py`
  - Include proper OpenAPI documentation
  - Use Pydantic models for request/response validation
- **Error Handling**:
  - Use `HTTPException` with descriptive messages
  - Log errors with context using `logger.error()`

### Commit Messages
Follow the conventional commits format:
```
type(scope): subject

body
```
Where:
- `type` = feat, fix, docs, style, refactor, test, chore, build, ci, revert
- `scope` = optional, specific component
- `subject` = brief description (imperative mood)

Example:
`feat(api): Add new health check endpoint`

## 🧪 Testing

### Unit Tests
- Place tests in `tests/` with naming convention `test_<module>.py`
- Use `pytest` framework
- Maintain >80% test coverage

### Integration Tests
- Place in `tests/integration/`
- Test interactions between components
- Use mock services where appropriate

### Mutation Testing
- Use `mutation-test.yml` for mutation testing
- Aim for >70% survival rate

## 📝 Documentation

### Style Guidelines
- Use Markdown format
- Follow Google Developer Style Guide
- Use clear headings and subheadings
- Include code examples where applicable
- Use consistent linking between documents

### New Features
For any new functionality:
1. Update `README.md` with usage instructions
2. Add API documentation to `docs/api-docs.md`
3. Create any necessary diagrams in `docs/`
4. Update validation plan in `VALIDATION.md`

## 🚀 Submitting Changes

1. **Create a Feature Branch**
   ```bash
   git checkout -b feat/new-feature
   ```

2. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "feat(api): Add new endpoint for job status"
   ```

3. **Push to Your Fork**
   ```bash
   git push origin feat/new-feature
   ```

4. **Create Pull Request**
   - Go to the repository on GitHub
   - Click "New Pull Request"
   - Fill in the template with:
     - Description of changes
     - Related issues (if any)
     - Testing information
     - Documentation changes
   - Request review from maintainers

## 🧑‍💻 Maintainers

Current maintainers:
- @netover (Primary Maintainer)

## 📚 Additional Resources

- [Code Review Guidelines](CODE_REVIEW_COMPREHENSIVE.md)
- [Security Policy](SECURITY.md)
- [Contributor Covenant Code of Conduct](CONDUCT.md)

## 🙌 Community

Join our community on:
- **Slack**: #resync-dev channel
- **Email**: resync-dev@hcl.tech
- **Meetings**: Bi-weekly contributor calls (schedule in README)

By following these guidelines, you help us maintain the high quality of Resync and make the contribution process smoother for everyone involved.



