# Change Log

## [0.5.0] - 2025-01-22

Synchronised with the [AZ AI Generator](https://github.com/dbroeglin/generator-az-ai).

### Added
- CHANGELOG.md
- Traceability through AI Foundry Tracing

### Changed
- Regenerated from scratch from the upstream [AZ AI Generator](https://github.com/dbroeglin/generator-az-ai)
- Updated backend to Semantic Kernel 1.19.0
- Updated backend telemetry dependencies to latest versions.

## Fixed
- The tracing processing logic

## [0.5.1] - 2025-01-27

### Added
- Ability to reference and use externally provisioned Azure OpenAI Models

### Changed
- Switched back to the SK chat completeion client as it now provides accurate agent names in tracing

## [0.5.2] - 2025-02-02

### Added
- patterns in the backend to be the first class abstractions
- Explicit LLM service roles - planner, executor, utility

### Changed
- Upgraded to SK 1.20.0
- It is possible to reference the externally provisioned OpenAI service (planner service only)

## [0.5.3] - 2025-03-03

### Changed
- Upgraded to SK 1.22.1