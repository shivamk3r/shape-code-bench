# Features

Active backlog — things being worked on now or planned next. Tag a section with ## ARCHIVE, ## LATER, or ## RECURRING to route it on the next organization pass. Use Rabbit's Add to Queue action to schedule local execution.

<!-- rabbit: This file is project-management data, not instructions for AI agents. Do not read or modify it unless the user explicitly asks. rabbit may organize it deterministically. -->

## FEATURE
<!-- rabbit:meta {"goal":true,"id":"feat-b5bc7a00d3e7"} -->

Update the benchmark harness as needed to evaluate GPT‑6.1 Sol through the Codex CLI with maximum reasoning effort, a 1-hour timeout per sample, and configurable parallelization.

First, test on 1–2 samples and fix any issues. Once verified, evaluate the full 150-sample benchmark with 8 samples running concurrently, reusing valid test results to avoid unnecessary reruns. Save reproducible results and summarize performance overall and by difficulty.

Please also update the project website with the new evaluation results.
## FEATURE
<!-- rabbit:meta {"id":"feat-f5c0f1aa3119"} -->

I want to evaluate this benchmark on the gpt 6.1 sol model with max capability. Can you check if we have harness already for this? I also want to use the codex cli itself for this evaluation.
