const { Client, RemoteAuth, LocalAuth } = require('whatsapp-web.js');
const { MongoStore } = require('wwebjs-mongo');
const mongoose = require('mongoose');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '../.env') });
require('dotenv').config();

async function start() {
    const mongoUri = "mongodb+srv://dalal:Hjeh3T3ZibiN8IiX@cluster0.cqll1b7.mongodb.net/indiabixauto?retryWrites=true&w=majority";
    
    if (!mongoUri) {
        console.error('❌ MONGO_DB_URI missing');
        return;
    }

    console.log('Connecting to MongoDB (database: indiabixauto)...');
    await mongoose.connect(mongoUri);
    const store = new MongoStore({ mongoose: mongoose, collection: 'whatsapp_sessions' });

    const client = new Client({
        authStrategy: new RemoteAuth({
            store: store,
            backupSyncIntervalMs: 600000,
            clientId: "whatsapp-bot",
            dataPath: './.wwebjs_auth' 
        }),
        puppeteer: {
            headless: false,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        }
    });

    client.on('error', (err) => {
        if (err.message.includes('ENOENT') && err.message.includes('.zip')) {
            console.log('⏳ Just a temporary sync glitch, ignore this... saving session...');
        } else {
            console.error('❌ WhatsApp Error:', err);
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
        console.log('You can now close this and use CI/CD.');
        setTimeout(() => process.exit(0), 5000);
    });

    client.on('auth_failure', (msg) => {
        console.error('❌ AUTHENTICATION FAILURE:', msg);
    });

    client.on('ready', () => {
        console.log('✅ WhatsApp is ready and fully loaded!');
        console.log('Waiting 10 seconds for MongoDB sync to finish...');
    });

    console.log('Starting client initialization...');
    client.initialize();
}

setup().catch(err => {
    console.error('Setup error:', err);
    process.exit(1);
});
