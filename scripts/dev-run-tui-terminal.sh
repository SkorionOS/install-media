#!/bin/bash
cd /home/gamer/git/install-media
export PYTHONPATH=/home/gamer/git/install-media/skorionos/airootfs/usr/local/lib
export TERM=xterm-256color
export COLORTERM=truecolor
export INSTALLER_DEV=1
export INSTALLER_SIMULATION=1
export INSTALLER_SIM_DISK=nvme0n1
export INSTALLER_FRZR_BOOTSTRAP=/home/gamer/git/install-media/scripts/installer-stubs/frzr-bootstrap
export INSTALLER_FRZR_DEPLOY=/home/gamer/git/install-media/scripts/installer-stubs/frzr-deploy
export INSTALLER_STUB_SLEEP=0
export INSTALLER_LOG_FILE=/tmp/frzr-tui-live.log
unset INSTALLER_SIM_AUTO
unset INSTALLER_DRY_RUN
exec python3 -m installer.tui_main
