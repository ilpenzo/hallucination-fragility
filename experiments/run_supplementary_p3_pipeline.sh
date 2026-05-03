#!/bin/bash
# run_supplementary_p3_pipeline.sh — Full pipeline for supplementary P3 scenarios
#
# Run this AFTER all 5 models have completed conversations.
# Steps: Score → Judge → Analyze
#
# Usage:
#   bash run_supplementary_p3_pipeline.sh

set -e

echo "============================================================"
echo "SUPPLEMENTARY P3 PIPELINE"
echo "============================================================"
echo ""

# Step 1: Score the responses (generates judge prompts)
echo "--- Step 1: Scoring responses ---"
python score_responses.py \
    --results-dir ./results_supplementary \
    --scenarios-dir ./p3_supplementary \
    --output-dir ./results_supplementary/scored_full

echo ""

# Step 2: Run P3 judge (~$1-2 for 40 entries)
echo "--- Step 2: Running P3 judge ---"
python run_p3_judge.py \
    --input-dir ./results_supplementary/scored_full \
    --output-dir ./results_supplementary/p3_judged

echo ""

# Step 3: Analyze fabrication results
echo "--- Step 3: Analyzing fabrication results ---"
python analyze_supplementary_p3.py \
    --p3-original-dir ./results/p3_judged/individual \
    --p3-supplementary-dir ./results_supplementary/p3_judged/individual \
    --output supplementary_p3_analysis.json

echo ""
echo "============================================================"
echo "PIPELINE COMPLETE"
echo "============================================================"
