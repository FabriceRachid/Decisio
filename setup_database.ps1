# PostgreSQL Database Setup Script for Decisio
# Run this AFTER installing PostgreSQL

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Decisio PostgreSQL Setup" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Prompt for PostgreSQL superuser password
$postgresPassword = Read-Host "Enter PostgreSQL 'postgres' user password"

# Prompt for new database user password
$newPassword = Read-Host "Choose a password for 'decisio_user'"

Write-Host ""
Write-Host "Creating database and user..." -ForegroundColor Yellow

# Create SQL commands
$sqlCommands = @"
CREATE DATABASE decisio_db;
CREATE USER decisio_user WITH PASSWORD '$newPassword';
GRANT ALL PRIVILEGES ON DATABASE decisio_db TO decisio_user;
\q
"@

# Execute in psql
$env:PGPASSWORD = $postgresPassword
$sqlCommands | & "C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Database created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 Now update backend\.env with:" -ForegroundColor Cyan
    Write-Host "   DB_PASSWORD=$newPassword" -ForegroundColor White
    Write-Host ""
    Write-Host "Then run:" -ForegroundColor Yellow
    Write-Host "   cd backend" -ForegroundColor White
    Write-Host "   python manage.py migrate" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "❌ Failed to create database. Check your PostgreSQL installation." -ForegroundColor Red
    Write-Host "Make sure PostgreSQL is installed and the password is correct." -ForegroundColor Yellow
}
