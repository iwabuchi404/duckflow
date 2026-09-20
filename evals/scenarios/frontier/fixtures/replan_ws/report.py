"""Generate an aggregated sales report via the external `chartgen` CLI."""

import subprocess


def main() -> None:
    # Aggregation is delegated to the chartgen tool.
    subprocess.run(
        ["chartgen", "--csv", "sales.csv", "--out", "report.txt"],
        check=True,
    )


if __name__ == "__main__":
    main()
