param(
    [Parameter(Position = 0)]
    [ValidateSet("build", "push", "run")]
    [string]$Command = "build",
    [Parameter(Position = 1)]
    [ValidateSet("aium")]
    [string]$Image = "aium",
    [Parameter(Position = 2)]
    [ValidateSet("jcode", "jcode-rust", "jcode-node", "opencode")]
    [string]$Tag = "jcode",
    [Parameter(Position = 3)]
    [string]$Deepseek_api_key = ""
)

switch ($Command) {
    "build" { 
        podman build -t "$($Image):$($Tag)" "./$($Image)/$($Tag)"
    }
    "push" {
        podman tag "localhost/$($Image):$($Tag)" "docker.io/k4rim/$($Image):$($Tag)"
        podman push "docker.io/k4rim/$($Image):$($Tag)"
    }
    "run" {
        podman run -it `
            -w /appum `
            -v "$(Get-Location):/appum" `
            -e DEEPSEEK_API_KEY="$($Deepseek_api_key)" `
            "docker.io/k4rim/$($Image):$($Tag)"
    }
    Default {}
}