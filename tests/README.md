# Testing

Tests located here will invoke the CliRunner that `click` provides.

https://click.palletsprojects.com/en/stable/testing/

These tests are more for testing the runner itself and ensuring input/output does not change unexpectedly.

Further testing exists within the individual scripts to test the functionality of those scripts regardless of the `click` integrations and/or API targets.

## Goals

- Assign extensive tests per root `cli` command:
  - Should have each of the sub commands covered
  - Tests each argument
  - Have comparisons for expected output both file and stdout
- Maintain tests as new features are added
- Ensure PR blocking to main in the event a given test fails
