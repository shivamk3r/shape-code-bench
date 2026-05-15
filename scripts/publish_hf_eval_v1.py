"""Publish the frozen eval_v1 dataset to the Hugging Face Hub.

Run with ephemeral upload dependencies, for example:

    uv run --with "datasets>=3.0" --with "huggingface_hub>=0.30" \
      python scripts/publish_hf_eval_v1.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from datasets import Dataset, DatasetDict, Image
from huggingface_hub import HfApi


DEFAULT_REPO_ID = "shivamk3r/shape-code-bench-eval-v1"
DEFAULT_DATASET_ROOT = Path("data/eval_v1")


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish ShapeCodeBench eval_v1 to Hugging Face.")
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID, help="Hugging Face dataset repo id.")
    parser.add_argument(
        "--dataset-root",
        default=str(DEFAULT_DATASET_ROOT),
        help="Path to the frozen eval_v1 dataset root.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and validate the dataset locally without uploading.",
    )
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root)
    dataset = build_dataset_dict(dataset_root)
    validate_dataset(dataset)

    if args.dry_run:
        print(dataset)
        print(dataset["eval"].features)
        return 0

    api = HfApi()
    api.create_repo(repo_id=args.repo_id, repo_type="dataset", private=False, exist_ok=True)
    dataset.push_to_hub(args.repo_id, private=False, commit_message="Publish ShapeCodeBench eval_v1")

    api.upload_file(
        repo_id=args.repo_id,
        repo_type="dataset",
        path_or_fileobj=str(dataset_root / "manifest.json"),
        path_in_repo="manifest.json",
        commit_message="Add eval_v1 manifest",
    )
    api.upload_file(
        repo_id=args.repo_id,
        repo_type="dataset",
        path_or_fileobj=str(dataset_root / "SHA256SUMS"),
        path_in_repo="SHA256SUMS",
        commit_message="Add eval_v1 checksums",
    )
    api.upload_file(
        repo_id=args.repo_id,
        repo_type="dataset",
        path_or_fileobj=dataset_card(args.repo_id).encode("utf-8"),
        path_in_repo="README.md",
        commit_message="Add ShapeCodeBench dataset card",
    )

    print(f"https://huggingface.co/datasets/{args.repo_id}")
    return 0


def build_dataset_dict(dataset_root: Path) -> DatasetDict:
    rows = build_rows(dataset_root)
    dataset = Dataset.from_list(rows).cast_column("image", Image())
    return DatasetDict({"eval": dataset})


def build_rows(dataset_root: Path) -> list[dict[str, Any]]:
    checksum_by_path = read_checksums(dataset_root / "SHA256SUMS")
    rows: list[dict[str, Any]] = []

    metadata_paths = sorted((dataset_root / "eval").glob("*/*.json"))
    if len(metadata_paths) != 150:
        raise ValueError(f"Expected 150 metadata files, found {len(metadata_paths)}")

    for metadata_path in metadata_paths:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        image_path = metadata_path.with_suffix(".png")
        if not image_path.exists():
            raise FileNotFoundError(f"Missing image for {metadata_path}: {image_path}")

        image_file_name = image_path.relative_to(dataset_root).as_posix()
        try:
            image_sha256 = checksum_by_path[image_file_name]
        except KeyError as exc:
            raise ValueError(f"Missing checksum for {image_file_name}") from exc

        rows.append(
            {
                "image": str(image_path),
                "image_file_name": image_file_name,
                "image_sha256": image_sha256,
                "sample_id": metadata["sample_id"],
                "split": metadata["split"],
                "difficulty": metadata["difficulty"],
                "seed": metadata["seed"],
                "image_size": metadata["image_size"],
                "num_shapes": metadata["num_shapes"],
                "shape_inventory": metadata["shape_inventory"],
                "ground_truth_program": metadata["ground_truth_program"],
                "render_config": metadata["render_config"],
            }
        )

    return rows


def read_checksums(path: Path) -> dict[str, str]:
    checksum_by_path: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative_path = line.split("  ", 1)
        checksum_by_path[relative_path] = digest
    return checksum_by_path


def validate_dataset(dataset: DatasetDict) -> None:
    eval_dataset = dataset["eval"]
    if len(eval_dataset) != 150:
        raise ValueError(f"Expected 150 eval rows, found {len(eval_dataset)}")
    image = eval_dataset[0]["image"]
    if image.size != (512, 512):
        raise ValueError(f"Expected 512x512 images, found {image.size}")


def dataset_card(repo_id: str) -> str:
    return f"""---
pretty_name: ShapeCodeBench eval_v1
license: cc-by-4.0
size_categories:
- n<1K
tags:
- image
- synthetic
- benchmark
- code-generation
- program-synthesis
- arxiv:2605.11680
---

# ShapeCodeBench eval_v1

This dataset is the frozen `eval_v1` reporting split for
[ShapeCodeBench](https://github.com/shivamk3r/shape-code-bench), a synthetic
benchmark for testing whether multimodal models can reconstruct executable
drawing programs from rendered shape images.

It contains 150 grayscale `512x512` PNG images: 50 `easy`, 50 `medium`, and
50 `hard` examples. Each row includes the rendered image, the canonical
ShapeCodeBench DSL program that generated it, generation metadata, render
configuration, and the SHA256 checksum for the source PNG.

Zenodo remains the archival release DOI:
<https://doi.org/10.5281/zenodo.20132286>. This Hugging Face dataset is a
discoverable and loadable mirror of the frozen evaluation split.

## Load

```python
from datasets import load_dataset

dataset = load_dataset("{repo_id}")
```

## Columns

- `image`: rendered target image.
- `image_file_name`: original path under `data/eval_v1`.
- `image_sha256`: checksum from `SHA256SUMS`.
- `sample_id`, `split`, `difficulty`, `seed`: sample identity and generation seed.
- `image_size`, `num_shapes`, `shape_inventory`: scene summary metadata.
- `ground_truth_program`: canonical ShapeCodeBench DSL program.
- `render_config`: deterministic V1 renderer configuration.

## Evaluation Hygiene

`eval_v1` is a frozen reporting split. Do not tune prompts, adapters, model
checkpoints, heuristic parameters, or generator settings on this split and then
report the result as clean held-out performance.

For development, generate separate train/dev splits from fresh seeds using the
ShapeCodeBench repository.

## Links

- Paper: <https://arxiv.org/abs/2605.11680>
- GitHub: <https://github.com/shivamk3r/shape-code-bench>
- Zenodo archived release: <https://doi.org/10.5281/zenodo.20132286>
- Artifact license: <https://github.com/shivamk3r/shape-code-bench/blob/main/LICENSE-ARTIFACTS.md>

## License

The generated benchmark dataset is licensed under CC BY 4.0. ShapeCodeBench
source code is licensed separately under MIT.
"""


if __name__ == "__main__":
    raise SystemExit(main())
