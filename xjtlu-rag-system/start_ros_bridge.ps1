param(
    [string]$RosDomainId = $env:ROS_DOMAIN_ID,
    [string]$CycloneDdsPeer = $env:CYCLONEDDS_PEER
)

# XJTLU RAG ROS2 voice bridge launcher
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  XJTLU ROS2 Voice Bridge" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ([string]::IsNullOrWhiteSpace($RosDomainId)) {
    $RosDomainId = "0"
}
$env:ROS_DOMAIN_ID = $RosDomainId

if (-not $env:CYCLONEDDS_URI) {
    if ([string]::IsNullOrWhiteSpace($CycloneDdsPeer)) {
        throw "Set CYCLONEDDS_PEER or CYCLONEDDS_URI before starting the ROS bridge."
    }
    $env:CYCLONEDDS_URI = '<CycloneDDS><Domain><General><AllowMulticast>false</AllowMulticast></General><Discovery><Peers><Peer address="{0}"/></Peers></Discovery></Domain></CycloneDDS>' -f $CycloneDdsPeer
}

if (-not $env:ROS_REPLY_TOPIC) {
    $env:ROS_REPLY_TOPIC = "/xjtlu_reply"
}
if (-not $env:ROS_REPLY_FORMAT) {
    $env:ROS_REPLY_FORMAT = "text"
}

Write-Host "ROS_DOMAIN_ID:    $env:ROS_DOMAIN_ID" -ForegroundColor Green
Write-Host "DDS peer/config:  configured" -ForegroundColor Green
Write-Host "ROS_REPLY_TOPIC:  $env:ROS_REPLY_TOPIC" -ForegroundColor Green
Write-Host "ROS_REPLY_FORMAT: $env:ROS_REPLY_FORMAT" -ForegroundColor Green
Write-Host ""
Write-Host "Subscribing:" -ForegroundColor Yellow
Write-Host "  /wake_word_event"
Write-Host "  /audio_msg"
Write-Host ""
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

python .\ros_bridge.py
