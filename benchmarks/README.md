# STT Benchmark Dataset Format

Use `scripts/benchmark_stt.py` with a CSV manifest to compare models/backends.

## Manifest Schema

Required columns:

- `audio`: path to a WAV file (absolute path or relative to `--audio-root`)
- `text`: reference transcript

Optional columns:

- `id`: stable sample identifier used in output

## Example

See `benchmarks/example_manifest.csv`.

## Run

```bash
uv run python scripts/benchmark_stt.py \
  --manifest benchmarks/example_manifest.csv \
  --audio-root benchmarks \
  --stt-backend nemo-canary \
  --model nvidia/canary-1b-flash \
  --device cuda \
  --language en
```
