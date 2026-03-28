#!/bin/bash

cd /Users/yjsoo/Documents/alphalab
source venv/bin/activate
export PYTHONPATH=/Users/yjsoo/Documents/alphalab/factor-lab:$PYTHONPATH
cd factor-lab
python3 scripts/run_backtest.py
