@echo off

pushd .
cd %~dp0.
setlocal

title mhm

if exist embed (
  embed\python -m mhm.main
) else (
  python -m mhm.main
)

endlocal
popd