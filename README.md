# ui-bench

`ui-bench` is a benchmark for testing how well multimodal models can look at a synthetic image and reconstruct the program that generated it.

The core task is simple:

1. We define a tiny, deterministic drawing framework for `512x512` images.
2. We generate programs made of simple shapes such as circles and squares.
3. Those programs render benchmark images.
4. A model sees the rendered image and must write code in the same framework.
5. We execute the predicted code, render the predicted image, and compare it with the original.

This gives us a controlled way to measure visual understanding plus program synthesis.

## Why This Benchmark

Most image understanding benchmarks stop at captions, labels, or multiple-choice answers. This project is different: the model must produce executable code that recreates the image.

That makes the task interesting for a few reasons:

- The benchmark is fully synthetic and can generate large amounts of data.
- Fresh evaluation sets can be generated on demand, which reduces the risk of benchmark contamination from fixed public examples.
- Ground-truth programs are known exactly.
- Difficulty can be scaled in a controlled way.
- Evaluation is objective because we can compare rendered outputs directly.
- The task measures perception, spatial reasoning, and structured code generation together.

## Proposed V1 Scope

The first version stays intentionally narrow so we can build a clean benchmark before expanding it.

- Canvas size: fixed at `512x512`
- Domain: 2D synthetic images
- Primitive shapes: `circle`, `filled_circle`, `square`, `filled_square`
- Initial color setup: white background with black shapes
- Rendering: deterministic draw order
- Output target: code written in a small benchmark-specific drawing DSL
- Execution model: restricted DSL parsing rather than arbitrary code execution
- Difficulty splits: `easy`, `medium`, `hard`

## Benchmark Loop

The benchmark pipeline will look like this:

1. Sample a scene specification from generator rules.
2. Convert that scene into canonical code in the benchmark DSL.
3. Render the image from the canonical code.
4. Give the image and DSL instructions to a model.
5. Parse and execute the model's predicted code.
6. Render the prediction.
7. Score the predicted render against the target render.
8. Aggregate results by model, split, and difficulty.

## What We Will Build

- A tiny rendering framework / DSL for shape-based images
- A dataset generator for easy, medium, and hard scenes
- A benchmark runner that queries different models
- An evaluator that executes predicted code and scores the output
- Reporting utilities for comparing models across splits and metrics

## Key Design Principles

- Image fidelity matters more than exact code string match.
- The rendering framework should be simple enough that syntax is not the main challenge.
- Dataset generation should be deterministic and reproducible from seeds.
- Difficulty should come from visual reasoning, not hidden prompt tricks.
- The benchmark should be easy to extend with more shapes, colors, and constraints later.
- The benchmark should support generating fresh unseen samples at evaluation time.

## Contamination Resistance

One of the biggest advantages of `ui-bench` is that the data does not need to be fixed forever.

Because the benchmark is synthetic, we can generate new images and programs on demand. If a released batch of examples becomes known or contaminated, we can evaluate on a brand-new set sampled from the same generator. That means the benchmark can keep producing fresh held-out tasks instead of depending entirely on one static dataset.

This does not make the benchmark permanently immune to models learning the general distribution, especially if the generator is public and widely used. But it does strongly reduce memorization of exact examples, which is a major practical advantage over static image benchmarks.

## Important Evaluation Insight

Two different programs can sometimes render the same image. Because of that, the primary metric should be based on rendered image similarity, not exact source-code equality.

Code-level checks are still useful, but they should be secondary. A strong model should get credit when it produces a different but visually equivalent program.

## Document Structure

- [README.md](README.md): project overview
- [docs/benchmark-spec.md](docs/benchmark-spec.md): deeper benchmark and implementation spec
- [AGENTS.md](AGENTS.md): working guidance for agents contributing to the project

## Current Status

This repository is currently in the definition phase. The next step is to implement the minimal drawing DSL, dataset generator, and evaluation harness described in the spec.
