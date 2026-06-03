$env:PYTHONPATH="src"
$env:RUN_ENV="local"
python -m biometeo_worker.main --slot manual
