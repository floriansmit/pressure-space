#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update
sudo apt-get install -y software-properties-common
sudo add-apt-repository -y ppa:opm/ppa
sudo apt-get update
sudo apt-get install -y mpi-default-bin libopm-simulators-bin python3-opm-common python3-opm-simulators
flow --version

