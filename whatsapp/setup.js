const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const fs = require('fs');
const path = require('path');

// This script is to be run LOCALLY once to generate your session.
const client = new Client({
    authStrategy: new LocalAuth({
        clientId: "whatsapp-bot"
    }),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox']
    }
});

client.on('qr', (qr) => {
    console.log('SCAN THIS QR CODE WITH YOUR WHATSAPP:');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('Client is ready!');
    console.log('SUCCESS: Your session is saved in the ".wwebjs_auth" folder.');
    console.log('Follow these steps now:');
    console.log('1. Close this script (Ctrl+C).');
    console.log('2. You will see a folder named ".wwebjs_auth".');
    console.log('3. I will provide a command to zip and encode this folder for GitHub Secrets.');
});

client.initialize();
