#!/bin/bash
# score_replication_pipeline.sh — Run the full scoring pipeline on replication results
#
# This replicates the exact pipeline used to produce the paper's canonical scores:
#   1. score_responses.py    → base scored_results.json
#   2. fix_p1_comprehensive  → fixes P1 "last number" extraction bug
#   3. p2_parser_fix2        → enhanced P2 plan parser
#   4. p2_rescore            → re-evaluates P2 constraints with enhanced parser
#   5. patch_p2_scores       → merges enhanced P2 into scored results
#
# Usage:
#   bash score_replication_pipeline.sh
#
# Prerequisites: All scoring scripts in project root. Replication results in
# ./results_replication/. Replication scenarios in ./replication_scenarios/.

set -e  # Exit on any error

RESULTS_DIR="./results_replication"
SCENARIOS_DIR="./replication_scenarios"
SCORED_DIR="./results_replication/scored_full"
P2_PARSER_DIR="./results_replication/p2_parser_analysis"
P2_RESCORE_DIR="./results_replication/p2_rescore_results"

echo "============================================================"
echo "REPLICATION SCORING PIPELINE"
echo "============================================================"
echo ""

# Step 1: Base scoring
echo "--- Step 1: Base scoring (score_responses.py) ---"
python score_responses.py \
    --results-dir "$RESULTS_DIR" \
    --scenarios-dir "$SCENARIOS_DIR" \
    --output-dir "$SCORED_DIR"
echo ""

# NOTE: We skip fix_p1_comprehensive.py here because the canonical
# scored_results_enhanced.json does NOT have the P1 fix baked in.
# The P1 fix (year-extraction bug) was applied separately to generate
# paper Table 1 numbers. Skipping it here keeps the comparison apples-to-apples.

# Step 2: Enhanced P2 parser
echo "--- Step 2: Enhanced P2 parser (p2_parser_fix2.py) ---"
python p2_parser_fix2.py \
    --results-dir "$RESULTS_DIR" \
    --scenarios-dir ./p2_scenarios \
    --output-dir "$P2_PARSER_DIR"
echo ""

# Step 3: P2 rescore with enhanced assignments
echo "--- Step 3: P2 rescore (p2_rescore.py) ---"
python p2_rescore.py \
    --results-dir "$RESULTS_DIR" \
    --scenarios-dir ./p2_scenarios \
    --enhanced-assignments "$P2_PARSER_DIR/p2_enhanced_assignments.json" \
    --output-dir "$P2_RESCORE_DIR"
echo ""

# Step 4: Patch enhanced P2 into base scored results
echo "--- Step 4: Patch P2 scores (patch_p2_scores.py) ---"
python patch_p2_scores.py \
    --scored-results "$SCORED_DIR/scored_results.json" \
    --rescore-detail "$P2_RESCORE_DIR/p2_rescore_per_scenario.json" \
    --output "$SCORED_DIR/scored_results_enhanced.json"
echo ""

echo "============================================================"
echo "PIPELINE COMPLETE"
echo "============================================================"
echo ""
echo "Final scored file: $SCORED_DIR/scored_results_enhanced.json"
echo ""
echo "Next step: compare against original scores:"
echo "  python compare_scored_replication.py \\"
echo "      --original ./results/scored_full/scored_results_enhanced.json \\"
echo "      --replication $SCORED_DIR/scored_results_enhanced.json \\"
echo "      --output replication_score_comparison.json"
