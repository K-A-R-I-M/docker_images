param(
    [Parameter(Position = 0)]
    [ValidateSet("build", "push")]
    [string]$Command = "build",
    [Parameter(Position = 1)]
    [ValidateSet("aium")]
    [string]$Image = "aium",
    [Parameter(Position = 2)]
    [ValidateSet("jcode", "opencode")]
    [string]$Tag = "jcode"
)

switch ($Command) {
    "build" { 
        podman build -t "$($Image):$($Tag)" "./$($Image)/$($Tag)"
    }
    "push" {
        podman tag "localhost/$($Image):$($Tag)" "docker.io/k4rim/$($Image):$($Tag)"
        podman push "docker.io/k4rim/$($Image):$($Tag)"
    }
    Default {}
}