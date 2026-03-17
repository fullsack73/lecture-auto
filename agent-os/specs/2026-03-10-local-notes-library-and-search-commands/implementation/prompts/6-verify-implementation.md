We're completing the verification process for Local Notes Library and Search Commands by performing the final end-to-end verification and producing the final verification report.

## Understand the context

Read @agent-os/specs/2026-03-10-local-notes-library-and-search-commands/spec.md to understand the full context of this spec.

## Your role

You are performing the final implementation verification using the **implementation-verifier** role.

## Perform final verification

Follow the implementation-verifier workflow to complete your verification:

### Step 1: Ensure tasks.md has been updated

Check `agent-os/specs/2026-03-10-local-notes-library-and-search-commands/tasks.md` and ensure that all tasks and their sub-tasks are marked as completed with `- [x]`.

If a task is still marked incomplete, then verify that it has in fact been completed by checking the following:
- Run a brief spot check in the code to find evidence that this task's details have been implemented
- Check for existence of an implementation report titled using this task's title in `agent-os/specs/2026-03-10-local-notes-library-and-search-commands/implementation/` folder.

IF you have concluded that this task has been completed, then mark it's checkbox and its' sub-tasks checkboxes as completed with `- [x]`.

IF you have concluded that this task has NOT been completed, then mark this checkbox with ⚠️ and note it's incompleteness in your verification report.


### Step 2: Verify that implementations and verifications have been documented

Check `agent-os/specs/2026-03-10-local-notes-library-and-search-commands/implementation` folder to confirm that each task group from this spec's `tasks.md` has an associated implementation document that is named using the number and title of the task group.

For example, if the 1st task group is titled "Library Service", then the implementer of that task group should have already created an implementation document named `agent-os/specs/2026-03-10-local-notes-library-and-search-commands/implementation/1-library-service-implementation.md`.

If documentation is missing for any task group, include this in your final verification report.


### Step 3: Update roadmap (if applicable)

Open `agent-os/product/roadmap.md` and check to see whether any item(s) match the description of the current spec that has just been implemented. If so, then ensure that these item(s) are marked as completed by updating their checkbox(s) to `- [x]`.


### Step 4: Run entire tests suite

Run the entire tests suite for the application so that ALL tests run. Verify how many tests are passing and how many have failed or produced errors.

Include these counts and the list of failed tests in your final verification report.

DO NOT attempt to fix any failing tests. Just note their failures in your final verification report.


### Step 5: Create final verification report

Create your final verification report in `agent-os/specs/2026-03-10-local-notes-library-and-search-commands/verification/final-verification.md`.
