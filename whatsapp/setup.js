const { Client, RemoteAuth, LocalAuth } = require('whatsapp-web.js');
const { MongoStore } = require('wwebjs-mongo');
const mongoose = require('mongoose');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../.env') });
require('dotenv').config();

async function setup() {
    const mongoUri = process.env.MONGO_DB_URI;
    if (!mongoUri) {
        console.error('❌ Error: MONGO_DB_URI not found in .env file.');
        process.exit(1);
    }

    console.log('Connecting to MongoDB...');
    await mongoose.connect(mongoUri);
    const store = new MongoStore({ mongoose: mongoose });

    const client = new Client({
        authStrategy: new RemoteAuth({
            store: store,
            backupSyncIntervalMs: 300000,
            clientId: "whatsapp-bot"
        }),
        puppeteer: {
            headless: false, // Show browser for setup
            args: ['--no-sandbox']
        }
    });

    client.on('qr', (qr) => {
        console.log('--------------------------------------------------');
        console.log('QR RECEIVED. Scan this with your WhatsApp:');
        console.log('--------------------------------------------------');
        const qrcode = require('qrcode-terminal');
        qrcode.generate(qr, { small: true });
    });

    client.on('authenticated', () => {
        console.log('✅ AUTHENTICATED: Login successful!');
    });

    client.on('remote_session_saved', () => {
        console.log('✅ REMOTE SESSION SAVED: Your session is now in MongoDB!');
        console.log('Checking your database for a collection named "whatsapp-auth"...');
        console.log('You can now close this and use CI/CD.');
        setTimeout(() => process.exit(0), 5000);
    });

    client.on('auth_failure', (msg) => {
        console.error('❌ AUTHENTICATION FAILURE:', msg);
        process.exit(1);
    });

    client.on('ready', () => {
        console.log('✅ WhatsApp is ready and fully loaded!');
    });

    console.log('Starting client initialization...');
    client.initialize();
}

setup().catch(err => {
    console.error('Setup error:', err);
    process.exit(1);
});
