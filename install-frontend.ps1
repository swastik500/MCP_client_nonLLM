# Install frontend dependencies
Write-Host "📦 Installing frontend dependencies..." -ForegroundColor Cyan
Write-Host ""

Set-Location frontend

if (Test-Path "node_modules") {
    Write-Host "✅ node_modules already exists, skipping..." -ForegroundColor Green
} else {
    Write-Host "Installing npm packages..." -ForegroundColor Yellow
    npm install
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Frontend dependencies installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "❌ Failed to install frontend dependencies" -ForegroundColor Red
        exit 1
    }
}

Set-Location ..

Write-Host ""
Write-Host "🎉 Setup complete! You can now run:" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend:  python main.py" -ForegroundColor Cyan
Write-Host "  Frontend: cd frontend && npm run dev" -ForegroundColor Cyan
Write-Host ""
Write-Host "Or use the quick start script:" -ForegroundColor Yellow
Write-Host "  .\start.bat" -ForegroundColor Cyan
