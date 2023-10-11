@echo off

pushd .
cd %~dp0.
setlocal

title Console

if exist embed (
  set python_env=embed\python
) else (
  set python_env=python 
)

%python_env% mhm-console.py

endlocal
popd