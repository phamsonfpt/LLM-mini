$env:PYTHONIOENCODING="utf-8"

Write-Host "Starting HotpotQA full benchmark (390 samples)..."
python -m src.evaluation.ragbench_eval hotpotqa 390
if ($LASTEXITCODE -ne 0) { Write-Host "HotpotQA failed" }

Write-Host "Starting MSMarco full benchmark (423 samples)..."
python -m src.evaluation.ragbench_eval msmarco 423
if ($LASTEXITCODE -ne 0) { Write-Host "MSMarco failed" }

Write-Host "Starting PubMedQA full benchmark (187 samples)..."
python -m src.evaluation.ragbench_eval pubmedqa 187
if ($LASTEXITCODE -ne 0) { Write-Host "PubMedQA failed" }

Write-Host "All benchmarks finished!"
