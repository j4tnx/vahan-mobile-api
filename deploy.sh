#!/bin/bash
set -e

echo "🚀 Starting Vahan API Deployment..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install dependencies for Ubuntu 24.04
echo "📥 Installing system dependencies..."
sudo apt install -y python3-pip python3-venv git curl wget unzip libnss3 libnspr4 libatk-bridge2.0-0t64 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2t64

# Install Chrome
echo "🌐 Installing Google Chrome..."
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y ./google-chrome-stable_current_amd64.deb
rm -f google-chrome-stable_current_amd64.deb

# Verify Chrome installation
echo "✅ Chrome version: $(google-chrome --version)"

# Change to project directory (assuming we're in vahan-mobile-api)
echo "📁 Setting up project directory..."
cd ~/vahan-mobile-api

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python packages
echo "📚 Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Make sure main.py and requirements.txt are in this directory
echo "📄 Checking required files..."
if [ ! -f "main.py" ]; then
    echo "❌ main.py not found in current directory!"
    echo "📝 Please make sure both main.py and requirements.txt are in ~/vahan-mobile-api/"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found in current directory!"
    exit 1
fi

# Create systemd service
echo "🔧 Creating systemd service..."
sudo cat > /etc/systemd/system/vahan-api.service << EOF
[Unit]
Description=Vahan Mobile Number API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/vahan-mobile-api
Environment=PATH=$HOME/vahan-mobile-api/venv/bin
ExecStart=$HOME/vahan-mobile-api/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 main:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start service
echo "🎯 Starting API service..."
sudo systemctl daemon-reload
sudo systemctl enable vahan-api
sudo systemctl start vahan-api

# Wait a moment for service to start
sleep 3

# Check service status
echo "📊 Checking service status..."
SERVICE_STATUS=$(sudo systemctl is-active vahan-api)

if [ "$SERVICE_STATUS" = "active" ]; then
    echo "✅ Deployment completed successfully!"
    echo ""
    echo "📋 Service Information:"
    echo "   Status: sudo systemctl status vahan-api"
    echo "   Logs: sudo journalctl -u vahan-api -f"
    echo "   Restart: sudo systemctl restart vahan-api"
    echo ""
    echo "🌐 API Endpoints:"
    echo "   Health Check: http://$(curl -s ifconfig.me):5000/health"
    echo "   Get Mobile: http://$(curl -s ifconfig.me):5000/api/get-mobile?reg_no=TEST123&chassis_last5=12345"
    echo ""
    echo "💡 Usage Examples:"
    echo "   GET: curl 'http://localhost:5000/api/get-mobile?reg_no=DL1ABC1234&chassis_last5=56789'"
    echo "   POST: curl -X POST http://localhost:5000/api/get-mobile -H 'Content-Type: application/json' -d '{\"reg_no\":\"DL1ABC1234\",\"chassis_last5\":\"56789\"}'"
else
    echo "❌ Service failed to start. Check logs with: sudo journalctl -u vahan-api -f"
    exit 1
fi
