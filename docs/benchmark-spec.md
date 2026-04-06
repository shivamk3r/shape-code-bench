# Benchmark Spec

## 1. Vision

`ui-bench` measures how well a model can reverse-engineer a simple visual scene into executable drawing code.

The benchmark is designed to answer a focused question:

> Given a rendered synthetic image, can a model infer the program that generated it well enough to recreate the same image?

This is not a general image-generation benchmark. It is a controlled perception-to-program benchmark.

## 2. Task Definition

Each benchmark example contains:

- A target image rendered at `512x512`
- The hidden ground-truth program that produced the image
- Metadata such as difficulty, seed, and scene attributes

At evaluation time:

1. The model receives the target image.
2. The model also receives the benchmark DSL description and output-format instructions.
3. The model returns code in the benchmark DSL.
4. The benchmark runner executes the predicted code in a sandboxed renderer.
5. The resulting image is compared with the original target image.

The benchmark score reflects how closely the prediction reproduces the target.

## 3. Recommended V1 Representation

For V1, the benchmark should use a tiny Python-based DSL rather than a full external graphics library.

Why this is the right starting point:

- It keeps the task focused on visual reasoning instead of library trivia.
- It makes execution deterministic.
- It reduces syntax noise.
- It gives us full control over allowed operations and canonical formatting.

Even if the syntax is Python-like, the evaluator should not execute arbitrary Python. It should parse a restricted AST or a narrow function-call format and then dispatch only approved drawing operations.

Recommended primitive API:

```python
filled_circle(cx=128, cy=128, radius=40)
circle(cx=300, cy=220, radius=60, stroke=4)
filled_square(cx=220, cy=360, size=80)
square(cx=380, cy=120, size=50, stroke=3)
```

Recommended V1 rules:

- Coordinate system uses integer pixel positions.
- `cx` and `cy` refer to center coordinates.
- `radius` is used for circles.
- `size` is the side length for squares.
- Hollow shapes require a `stroke` width.
- Shapes are drawn in program order.
- Shapes that extend beyond the canvas are clipped deterministically.
- Initial palette is binary: white background, black foreground.
- The evaluator accepts only a restricted subset of the DSL, not general Python.

## 4. Dataset Generation

Each sample should be generated from a latent scene specification, then converted into canonical code.

Suggested generation pipeline:

1. Choose a difficulty tier.
2. Sample the number of shapes and scene constraints for that tier.
3. Sample shape types, positions, sizes, fill mode, and draw order.
4. Convert the scene into a canonical DSL program.
5. Render the image from that program.
6. Save image, program, and metadata.

One major benefit of this setup is that the dataset can be regenerated continuously. The benchmark does not need to rely on a single frozen corpus of images. Fresh samples can be created on demand for new evaluation runs.

Suggested metadata fields:

- `sample_id`
- `split`
- `difficulty`
- `seed`
- `image_size`
- `num_shapes`
- `shape_inventory`
- `ground_truth_program`
- `render_config`

## 5. Difficulty Tiers

The benchmark should support at least three initial tiers.

### Easy

- `1-3` shapes
- Large shapes
- Minimal or no overlap
- Shapes away from canvas boundaries
- Limited variation in stroke width

### Medium

- `3-6` shapes
- Moderate size variation
- Some overlap
- Mixed filled and hollow shapes
- More varied placements across the canvas

### Hard

- `6-10` shapes
- Heavy overlap or nesting
- Small and large shapes mixed together
- Shapes near edges or partially clipped
- Ambiguous layouts where draw order matters

Difficulty should come from compositional visual complexity, not from changing the DSL itself.

## 6. Evaluation

### Primary Metrics

The primary score should be render-based.

Recommended metrics:

- Exact pixel match rate
- Pixel accuracy
- Foreground IoU
- Mean score by difficulty tier

For this benchmark family, simple render-based metrics are more useful than generic perceptual scores because the images are synthetic and geometrically crisp.

### Secondary Metrics

- Program execution success rate
- Parse success rate
- Canonical format compliance
- Optional parameter-level recovery accuracy if scene metadata is exposed internally

### Important Principle

Source-code exact match should not be the main score.

Reason:

- Multiple programs may be visually equivalent.
- Small formatting differences should not matter.
- The benchmark is intended to measure scene understanding, not memorization of one textual form.

## 7. Prompting Protocol

To compare models fairly, the harness should standardize the evaluation prompt.

Each model should receive:

- The target image
- A short description of the allowed DSL
- A strict instruction to return code only
- The same formatting template across models

Recommended prompt constraints:

- No chain-of-thought requested
- No explanation in output
- Temperature fixed or standardized
- A max output length that covers the DSL comfortably

## 8. Splits And Benchmark Hygiene

Suggested splits:

- `train`
- `validation`
- `test_public`
- `test_hidden`

Good benchmark hygiene matters:

- Use fixed seeds for released datasets.
- Keep hidden test programs private if public leaderboards are added.
- Version the dataset generator so benchmark updates are traceable.
- Log renderer and prompt versions for every evaluation run.
- Support generating fresh held-out evaluation sets from new seeds when contamination is suspected.

## 8.1 Contamination Resistance

Synthetic generation is one of the benchmark's strongest differentiators.

If a fixed set of benchmark images becomes overexposed, we can generate a new evaluation set from unseen seeds and continue measuring on fresh examples. This is a meaningful advantage over static benchmarks, where leaked or memorized examples can permanently damage the usefulness of the test set.

Important nuance:

- This reduces contamination of exact instances.
- It does not fully prevent models from learning the generator's overall distribution.
- Hidden evaluation seeds and periodic refreshes will still be important for maintaining benchmark quality.

## 9. Canonicalization

Canonicalization will make both generation and evaluation cleaner.

Suggested rules:

- Use one function call per line.
- Use a fixed argument order.
- Use integer parameters only in V1.
- Use normalized whitespace.
- Keep imports and boilerplate minimal or fully fixed.

Canonicalization helps reduce parsing errors and makes it easier to inspect predictions manually.

## 10. Failure Cases To Handle

The benchmark runner should explicitly handle:

- Invalid syntax
- Unsupported function names
- Missing required arguments
- Out-of-range values
- Non-terminating or unsafe code

If execution fails, the example should be marked as invalid prediction and scored accordingly.

## 11. Initial Milestones

Suggested build order:

1. Implement the minimal drawing DSL and deterministic renderer.
2. Implement canonical program serialization.
3. Implement dataset generation for `easy`, `medium`, and `hard`.
4. Implement evaluation by re-rendering predicted code.
5. Add one or two model adapters for end-to-end testing.
6. Add reporting scripts for aggregate benchmark tables.

## 12. Proposed Repository Shape

One reasonable layout for the implementation phase:

```text
ui-bench/
  README.md
  docs/
    benchmark-spec.md
  src/
    renderer/
    dsl/
    generator/
    evaluator/
    adapters/
  data/
    samples/
    generated/
  scripts/
```

## 13. Expansion Paths

Once V1 is stable, the benchmark can expand to include:

- Additional shapes such as triangles or rectangles
- Multiple colors
- Rotation
- Layering-heavy scenes
- Symmetry and repetition patterns
- Text or labels
- Natural-language scene descriptions paired with code

Those should come after the simple-shape benchmark is reliable.

## 14. Recommended Product Framing

A concise way to describe the project:

`ui-bench` is a synthetic multimodal benchmark for measuring how accurately models can infer executable drawing programs from rendered geometric scenes.

## 15. Decision Summary For V1

These are the recommended default decisions unless we intentionally change them:

- Use a benchmark-owned Python DSL
- Fix image size at `512x512`
- Start with circles and squares only
- Use filled and hollow variants
- Use black shapes on white background
- Score primarily by rendered image similarity
- Provide `easy`, `medium`, and `hard` difficulty tiers

## 16. Immediate Next Step

The next implementation step should be to define the exact DSL API and build the renderer around it. Once that exists, dataset generation and evaluation become straightforward.
