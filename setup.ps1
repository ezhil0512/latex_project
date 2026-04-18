$ErrorActionPreference = "Stop"

Write-Host "Creating virtual environment..."
python -m venv .venv

Write-Host "Installing Python packages..."
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (!(Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env. Edit DATABASE_URL with your PostgreSQL password."
}

Write-Host "Setup complete."
Write-Host "Run: .\.venv\Scripts\python.exe app.py"
