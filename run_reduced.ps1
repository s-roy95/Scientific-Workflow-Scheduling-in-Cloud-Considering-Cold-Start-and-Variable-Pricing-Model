# Comparison plan: 6 approaches (random baselines excluded) x 3 workflows
#   workflows: log_processing (linear, light), video_processing (fan-out),
#              staircase_chain (42-step deep chain)
#   approaches: FaasCache, DCD(D), CEWB, DCD(R+D), DCD(R+D+S), DCD-Pred
# Usage:
#   .\run_reduced.ps1 -Calibrate     # once (calibrates the 3 workflows)
#   .\run_reduced.ps1 6              # experiments with 6 instances each
param([int]$Instances = 6, [switch]$Calibrate)

$workflows = @("log_processing","video_processing","staircase_chain")
$policies  = @("d_sota","d_dcd","ds_sota2","rd_dcd","rds_dcd","rds_dcd_pred")

if ($Calibrate) {
    foreach ($w in $workflows) {
        Write-Host "`n=== calibrating $w ===" -ForegroundColor Yellow
        python run_dag_workflow.py --workflow $w --calibrate
    }
    exit
}

foreach ($w in $workflows) {
    foreach ($p in $policies) {
        Write-Host "`n=== $w / $p ===" -ForegroundColor Cyan
        python run_dag_workflow.py --workflow $w --policy $p --instances $Instances
    }
}

$rows = foreach ($w in $workflows) { foreach ($p in $policies) {
    $f = "results/dag_${w}_${p}_${Instances}inst_seed42_summary.csv"
    if (Test-Path $f) { Import-Csv $f }
}}
Write-Host "`n=== COMBINED: 6 approaches x 3 workflows ===" -ForegroundColor Green
$rows | Format-Table workflow,policy,total_cost,profit,deadlines_missed,cold_starts,tasks_on_reserved,tasks_on_ondemand,tasks_on_spot,measured_transfer_s -AutoSize
$rows | Export-Csv "results/comparison_6approaches_3workflows_${Instances}inst.csv" -NoTypeInformation
Write-Host "Saved: results/comparison_6approaches_3workflows_${Instances}inst.csv"
