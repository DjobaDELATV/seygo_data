#!/usr/bin/env python3
"""Merge temp cache directories from parallel Yugipedia partition jobs into one.

Usage: merge_temp_caches.py <output_dir> <partition_dir1> [partition_dir2 ...]

Each partition dir is expected to contain the yugipedia cache JSON files produced
by a parallel yugipedia import job. The merged result is written to output_dir.
"""
import json
import os
import sys


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def merge_temp_caches(output_dir: str, partition_dirs: list):
    os.makedirs(output_dir, exist_ok=True)

    # yugipedia_pages.json: list of {id, name} — merge by id, last partition wins
    pages: dict = {}
    for d in partition_dirs:
        for entry in load_json(os.path.join(d, "yugipedia_pages.json"), []):
            pages[entry["id"]] = entry["name"]
    with open(
        os.path.join(output_dir, "yugipedia_pages.json"), "w", encoding="utf-8"
    ) as f:
        json.dump([{"id": k, "name": v} for k, v in pages.items()], f, indent=2)

    # dict-based caches — partitions have disjoint page IDs so no real conflicts
    for filename in [
        "yugipedia_contents.json",
        "yugipedia_categories.json",
        "yugipedia_images.json",
    ]:
        merged: dict = {}
        for d in partition_dirs:
            merged.update(load_json(os.path.join(d, filename), {}))
        with open(os.path.join(output_dir, filename), "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2)

    # yugipedia_members.json: category member lists — same across partitions, merge is safe
    members: dict = {}
    for d in partition_dirs:
        members.update(load_json(os.path.join(d, "yugipedia_members.json"), {}))
    with open(
        os.path.join(output_dir, "yugipedia_members.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(members, f, indent=2)

    # yugipedia_missing.json: list of str — union
    missing: set = set()
    for d in partition_dirs:
        missing.update(load_json(os.path.join(d, "yugipedia_missing.json"), []))
    with open(
        os.path.join(output_dir, "yugipedia_missing.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(list(missing), f, indent=2)

    print(f"Merged {len(partition_dirs)} partition caches into '{output_dir}'")
    print(f"  Pages indexed:     {len(pages)}")
    print(f"  Category members:  {len(members)}")
    print(f"  Missing pages:     {len(missing)}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            f"Usage: {sys.argv[0]} <output_dir> <partition_dir1> [partition_dir2 ...]"
        )
        sys.exit(1)
    merge_temp_caches(output_dir=sys.argv[1], partition_dirs=sys.argv[2:])
