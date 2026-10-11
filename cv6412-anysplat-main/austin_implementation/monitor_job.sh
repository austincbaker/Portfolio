

JOB_ID=${1:?Usage: $0 <job_id> [output_file]}
OUTPUT_FILE=${2:-"eval_${JOB_ID}.out"}
ERROR_FILE=${OUTPUT_FILE%.out}.err
INTERVAL=60
TAIL_LINES=20
LAST_ERROR_SIZE=0

timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

log() {
    echo "[$(timestamp)] $1"
}

check_for_new_errors() {
    if [[ -f "$ERROR_FILE" ]]; then
        CURRENT_SIZE=$(stat -c%s "$ERROR_FILE" 2>/dev/null || stat -f%z "$ERROR_FILE" 2>/dev/null)
        if [[ "$CURRENT_SIZE" -gt "$LAST_ERROR_SIZE" ]]; then
            log "WARNING: New content in error file detected!"
            return 0
        fi
    fi
    return 1
}

log "Starting monitor for job $JOB_ID"
log "Output file: $OUTPUT_FILE"
log "Error file: $ERROR_FILE"
log "Check interval: $((INTERVAL / 60)) minutes"
echo "----------------------------------------"

while true; do
    echo $(date +"%T")
    JOB_INFO=$(squeue -j "$JOB_ID" -h -o "%T %M %N" 2>/dev/null)
    
    if [[ -z "$JOB_INFO" ]]; then
        FINAL_STATE=$(sacct -j "$JOB_ID" -n -o State,ExitCode -X 2>/dev/null | head -1 | xargs)
        log "Job $JOB_ID finished. Final state: ${FINAL_STATE:-UNKNOWN}"
        
        if [[ -f "$OUTPUT_FILE" ]]; then
            log "Final output tail:"
            tail -n "$TAIL_LINES" "$OUTPUT_FILE"
        fi
        if [[ -f "$ERROR_FILE" && -s "$ERROR_FILE" ]]; then
            log "Final error tail:"
            tail -n "$TAIL_LINES" "$ERROR_FILE"
        fi
        
        # Exit with non-zero if job failed
        if [[ "$FINAL_STATE" == *"FAILED"* || "$FINAL_STATE" == *"TIMEOUT"* || "$FINAL_STATE" == *"CANCELLED"* ]]; then
            log "Job did not complete successfully."
            exit 1
        fi
        
        log "Monitor complete."
        exit 0
    fi
    
    STATE=$(echo "$JOB_INFO" | awk '{print $1}')
    ELAPSED=$(echo "$JOB_INFO" | awk '{print $2}')
    NODE=$(echo "$JOB_INFO" | awk '{print $3}')
    
    log "Status: $STATE | Elapsed: $ELAPSED | Node: $NODE"
    
    if [[ "$STATE" == "RUNNING" ]]; then
        if check_for_new_errors; then
            log "Error file content:"
            tail -n "$TAIL_LINES" "$ERROR_FILE"
            LAST_ERROR_SIZE=$(stat -c%s "$ERROR_FILE" 2>/dev/null || stat -f%z "$ERROR_FILE" 2>/dev/null)
        fi
        
        if [[ -f "$OUTPUT_FILE" ]]; then
            log "Output tail (last $TAIL_LINES lines):"
            tail -n "$TAIL_LINES" "$OUTPUT_FILE"
        fi
    elif [[ "$STATE" == "PENDING" ]]; then
        START_TIME=$(squeue -j "$JOB_ID" -h -o "%S" 2>/dev/null)
        REASON=$(squeue -j "$JOB_ID" -h -o "%R" 2>/dev/null)
        log "Job pending, waiting for resources..."
        if [[ -n "$START_TIME" && "$START_TIME" != "N/A" ]]; then
            log "Estimated start time: $START_TIME"
        fi
        if [[ -n "$REASON" ]]; then
            log "Reason: $REASON"
        fi
    fi
    
    echo "----------------------------------------"
    log "Next check in $((INTERVAL / 60)) minutes..."
    sleep "$INTERVAL"

    echo $(date +"%T")
done
