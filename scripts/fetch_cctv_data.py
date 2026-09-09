"""서울 25개 자치구 불법주정차 단속 CCTV를 내려받아 가공본으로 저장한다."""

from __future__ import annotations

import argparse
import csv
import gzip
import os
from pathlib import Path

from dotenv import load_dotenv

from src.data_sources.seoul import SeoulIllegalParkingCctvAdapter, SeoulOpenApiClient

FIELDS = [
    "district",
    "address",
    "location",
    "category",
    "latitude",
    "longitude",
    "service",
    "is_sample",
]


def fetch_and_write(api_key: str, output: Path) -> int:
    records = SeoulIllegalParkingCctvAdapter(SeoulOpenApiClient(api_key)).list_records()
    output.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/processed/cctv.csv.gz"))
    args = parser.parse_args()
    load_dotenv()
    api_key = os.getenv("SEOUL_OPEN_API_KEY", "")
    if not api_key:
        raise SystemExit("SEOUL_OPEN_API_KEY가 필요합니다.")
    count = fetch_and_write(api_key, args.output)
    print(f"cctv.csv.gz: {count:,} rows")


if __name__ == "__main__":
    main()
