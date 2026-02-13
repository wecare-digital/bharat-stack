# Deep check all live Velo endpoints and site structure
$base = "https://www.wecare.digital"
$out = ""

$endpoints = @(
    @{ name = "siteinfo"; url = "/_functions/siteinfo" },
    @{ name = "discovery"; url = "/_functions/discovery" },
    @{ name = "faq"; url = "/_functions/faq" },
    @{ name = "contact"; url = "/_functions/contact" },
    @{ name = "robots"; url = "/_functions/robots" },
    @{ name = "seohead-home"; url = "/_functions/seohead?path=/" },
    @{ name = "seohead-nofault"; url = "/_functions/seohead?path=/no-fault" },
    @{ name = "seohead-bnb"; url = "/_functions/seohead?path=/bnb" },
    @{ name = "seohead-ritual"; url = "/_functions/seohead?path=/ritual" },
    @{ name = "seohead-swdhya"; url = "/_functions/seohead?path=/swdhya" },
    @{ name = "seohead-legal"; url = "/_functions/seohead?path=/legal-champ" },
    @{ name = "keywordscloud"; url = "/_functions/keywordscloud" },
    @{ name = "icons"; url = "/_functions/icons" },
    @{ name = "rss"; url = "/_functions/rss" },
    @{ name = "diag"; url = "/_functions/diag" },
    @{ name = "seoerrors"; url = "/_functions/seoerrors" }
)

foreach ($ep in $endpoints) {
    Start-Sleep -Milliseconds 1500
    try {
        $r = Invoke-WebRequest -Uri "$base$($ep.url)" -Method GET -UseBasicParsing -TimeoutSec 15
        $preview = $r.Content.Substring(0, [Math]::Min(500, $r.Content.Length))
        $out += "=== $($ep.name) ($($r.StatusCode)) ===`n$preview`n`n"
    } catch {
        $status = "ERR"
        if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode }
        $out += "=== $($ep.name) ($status) ===`n$($_.Exception.Message.Substring(0, [Math]::Min(100, $_.Exception.Message.Length)))`n`n"
    }
}

$out | Out-File -FilePath "scripts/deep-check-results.txt" -Encoding utf8
Write-Output "Done. Results saved."
