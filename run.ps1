param(
    [Parameter(Position = 0)]
    [ValidateSet("build", "push")]
    [string]$Command = "build",
    [Parameter(Position = 1)]
    [ValidateSet("aium")]
    [string]$Image = "aium"
)

switch ($Command) {
    "build" { 
        podman build -t $Image ./$Image
    }
    "push" {
        podman tag localhost/$Image docker.io/k4rim/$Image
        podman push docker.io/k4rim/$Image
    }
    Default {}
}