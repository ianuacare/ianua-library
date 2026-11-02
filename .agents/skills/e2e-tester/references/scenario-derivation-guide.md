# Scenario Derivation Guide

How to transform existing spec artifacts into testable E2E scenarios.

## General Principles

- **One scenario = one user journey**, not one click or one page
- A scenario may reference multiple source specs (e.g., a PRD + a user flow + a wireframe)
- Always use **Gherkin syntax** (`Given/When/Then`) for the step definitions
- Reference `FLOW-NNN` Mermaid diagrams for visual context — do not duplicate them in the scenario
- Each acceptance criterion in a PRD should be covered by at least one scenario step

## From PRD User Stories (PRD-NNN)

PRDs contain user stories with acceptance criteria. Each acceptance criterion maps to one or more assertions in a scenario.

**Pattern**:

1. Read the PRD's user stories section
2. For each user story, identify the **happy path** acceptance criteria → these become the primary scenario
3. Identify **edge case** acceptance criteria → these become alternative scenarios
4. Map each acceptance criterion to a `Then` assertion

**Example**:

PRD user story:
> As a registered user, I want to reset my password so I can regain access to my account.
> - AC1: User receives a reset email within 60 seconds
> - AC2: Reset link expires after 24 hours
> - AC3: New password must meet strength requirements

Derived scenarios:

```gherkin
Scenario: Password reset happy path (covers AC1)
  Given the user is on the /forgot-password page
  When they enter their registered email
    And click "Send reset link"
  Then they see a confirmation message
    And they receive a reset email within 60 seconds

Scenario: Reset link expiration (covers AC2)
  Given the user received a reset link 25 hours ago
  When they click the reset link
  Then they see an "expired link" error
    And are prompted to request a new reset

Scenario: Password strength validation (covers AC3)
  Given the user clicked a valid reset link
  When they enter a weak password (e.g., "123")
  Then they see a strength validation error
    And the password is not changed
```

## From User Flows (FLOW-NNN)

User flows contain Mermaid diagrams with happy paths, alternative flows, and exception flows. Each flow path maps to a scenario.

**Pattern**:

1. Read the Mermaid diagram in `FLOW-NNN`
2. The **happy path** (main flow) becomes the primary scenario
3. Each **alternative flow** branch becomes an alternative scenario
4. Each **exception flow** (error handling) becomes an error scenario
5. Reference the flow: `Source: FLOW-NNN-slug`

**Example**:

A checkout flow with branches for "guest checkout" and "registered user checkout":

```gherkin
Scenario: Registered user checkout (happy path from FLOW-003)
  Given the user is logged in
    And has items in the cart
  When they proceed to checkout
    And confirm the saved shipping address
    And select a payment method
    And click "Place order"
  Then they see an order confirmation page
    And receive a confirmation email

Scenario: Guest checkout (alternative flow from FLOW-003)
  Given the user is not logged in
    And has items in the cart
  When they proceed to checkout
    And enter shipping details manually
    And enter payment details
    And click "Place order"
  Then they see an order confirmation page
    And are offered to create an account
```

## From Use Cases (UC-NNN)

Use case narratives provide structured scenarios with actors, triggers, and postconditions. They map almost directly to Gherkin.

**Pattern**:

1. Read the use case narrative
2. The **main success scenario** becomes the primary Gherkin scenario
3. The **trigger** becomes the first `When` step
4. The **postconditions** become `Then` assertions
5. **Alternative flows** and **exception flows** become separate scenarios

**Mapping**:

| Use Case Element | Gherkin Element |
|-----------------|-----------------|
| Preconditions | `Given` steps |
| Trigger | First `When` step |
| Main success steps | `When` / `And` steps |
| Postconditions | `Then` assertions |
| Alternative flows | Separate `Scenario` blocks |
| Exception flows | Separate `Scenario` blocks with error assertions |

## From Wireframes (WF-NNN)

Wireframes define interface states and interaction patterns. Each state implies assertions during the E2E flow.

**Pattern**:

1. Read the wireframe and its states (default, empty, loading, error, success)
2. For each state, add assertions to relevant scenarios
3. Interaction notes in the wireframe map to `When` steps
4. Component inventory maps to existence assertions

**State-to-Assertion mapping**:

| Wireframe State | Scenario Assertion |
|----------------|-------------------|
| Default state | `Then the {component} is visible with default content` |
| Empty state | `Given no data exists` → `Then the empty state message is shown` |
| Loading state | `When the page loads` → `Then a loading indicator is visible` |
| Error state | `When the API returns an error` → `Then the error message is displayed` |
| Success state | `When the action completes` → `Then the success feedback is shown` |

## Scenario Granularity Guidelines

- **Too granular** (avoid): one scenario per button click or field input
- **Right level**: one scenario per meaningful user outcome (login, purchase, password reset)
- **Too broad** (avoid): one scenario covering an entire user session across multiple features

A good scenario should be:
- **Independent**: can run without other scenarios completing first (unless explicitly documented)
- **Deterministic**: same inputs always produce the same result
- **Complete**: tests a full journey from entry point to observable outcome
- **Traceable**: references the source specs that define the expected behavior
