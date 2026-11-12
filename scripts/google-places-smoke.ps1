param(
    [switch]$IUnderstandMayBeBilled,
    [int]$MaxCalls = 3
)
$ErrorActionPreference = "Stop"
if (-not $IUnderstandMayBeBilled) { throw "Must explicitly pass -IUnderstandMayBeBilled; Google API may be billed." }
if ($MaxCalls -lt 2 -or $MaxCalls -gt 3) { throw "MaxCalls must be 2 or 3. No more than three live calls." }
$key = [Environment]::GetEnvironmentVariable('GOOGLE_MAPS_API_KEY')
if ([string]::IsNullOrWhiteSpace($key)) { throw "Set GOOGLE_MAPS_API_KEY locally. Never paste it into source files or chat." }
$endpoint = 'https://places.googleapis.com/v1'
$baseFields = 'places.id,places.displayName,places.googleMapsUri,places.attributions'
$results = @()
$script:called = 0
function Invoke-BoundedGoogle {
    param([string]$Method, [string]$Url, [object]$Body, [string]$Fields, [string]$Label)
    if ($script:called -ge $MaxCalls) { throw "Call budget exceeded." }
    $script:called += 1
    $headers = @{ 'X-Goog-Api-Key'=$key; 'X-Goog-FieldMask'=$Fields }
    $start = [Diagnostics.Stopwatch]::StartNew()
    try {
        if ($null -eq $Body) { $response = Invoke-RestMethod -Uri $Url -Method $Method -Headers $headers -TimeoutSec 12 }
        else { $response = Invoke-RestMethod -Uri $Url -Method $Method -Headers $headers -Body ($Body | ConvertTo-Json -Depth 12) -ContentType 'application/json; charset=utf-8' -TimeoutSec 12 }
        $start.Stop()
        $count = if ($null -ne $response.places) { @($response.places).Count } else { 1 }
        Write-Host "${Label}: status=OK; count=$count; elapsedMs=$($start.ElapsedMilliseconds)"
        return $response
    } catch {
        $start.Stop()
        $statusCode = 'HTTP_ERROR'
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) { $statusCode = [int]$_.Exception.Response.StatusCode }
        Write-Host "${Label}: status=$statusCode; elapsedMs=$($start.ElapsedMilliseconds); raw payload suppressed"
        throw "Stopped after ${Label} failure. No retries. Inspect Google Cloud Billing/Logs securely."
    }
}
# Test location is a generic center in HCMC. User GPS is never required.
$nearbyBody = @{
  includedTypes = @('restaurant')
  maxResultCount = 5
  rankPreference = 'DISTANCE'
  locationRestriction = @{ circle = @{ center = @{ latitude = 10.7769; longitude = 106.7009 }; radius = 500.0 } }
}
$nearby = Invoke-BoundedGoogle -Method 'Post' -Url "$endpoint/places:searchNearby" -Fields $baseFields -Label 'NEARBY_PRO' -Body $nearbyBody
$textBody = @{
  textQuery = 'pho'
  pageSize = 5
  locationBias = @{ circle = @{ center = @{ latitude = 10.7769; longitude = 106.7009 }; radius = 500.0 } }
}
$text = Invoke-BoundedGoogle -Method 'Post' -Url "$endpoint/places:searchText" -Fields $baseFields -Label 'TEXT_PRO' -Body $textBody
if ($MaxCalls -ge 3) {
  $id = $null
  if ($nearby.places -and @($nearby.places).Count -gt 0) { $id = @($nearby.places)[0].id }
  if ($id) {
    # URL-encode path segment; use only ID supplied by Google; don't log it.
    $safe = [Uri]::EscapeDataString([string]$id)
    $null = Invoke-BoundedGoogle -Method 'Get' -Url "$endpoint/places/$safe" -Fields 'id,displayName,googleMapsUri,attributions' -Label 'DETAILS_PRO' -Body $null
  } else { Write-Host 'DETAILS: skipped (Nearby returned no IDs).' }
}
Write-Host "Done. Actual outbound calls=$script:called. Confirm SKU/usage in Google Cloud Billing Console (not inferred from HTTP alone)."
