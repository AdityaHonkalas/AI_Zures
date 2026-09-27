$base64Certs = Get-ChildItem -Path Cert:\LocalMachine\Root | Select -Unique | ForEach-Object {
@"
# Issuer: $($_.Issuer)
# Subject: $($_.Subject)
-----BEGIN CERTIFICATE-----
$([Convert]::ToBase64String($_.Export('Cert'), [System.Base64FormattingOptions]::InsertLineBreaks))
-----END CERTIFICATE-----
"@
}

$certsString = $base64Certs -join "`n`n"

$certFileName = "generated-cert-bundle.pem"
$certFile = New-Item -Path $HOME -Name $certFileName -ItemType File -Value $certsString -Force

[Environment]::SetEnvironmentVariable("SSL_CERT_FILE", $certFile.FullName, "User")
[Environment]::SetEnvironmentVariable("REQUESTS_CA_BUNDLE", $certFile.FullName, "User")

Write-Output "Certificate bundle created at: $($certFile.FullName)"