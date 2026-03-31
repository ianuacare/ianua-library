# Backend Quality Standards

## Size and Complexity
- Function target: <= 30 lines (soft limit)
- Module/class target: cohesive responsibility, avoid "god modules"
- Branching complexity: keep low; prefer guard clauses

## Testing
- New behavior should include tests
- API changes must include contract-level assertions
- Critical flows (auth/clinical decisions) require stronger coverage

## Flask Conventions
- Use app factory and blueprints
- Keep route handlers thin
- Centralize error mapping into JSON response format

## ianua-library Integration
- Wrap library calls in dedicated adapters/services
- Define explicit timeout/retry strategy at integration boundary
- Convert library exceptions to typed domain/app errors

## Security Baseline
- Zero tolerance for leaked secrets and PII logs
- Enforce authorization scope checks
- Validate all externally controlled input
