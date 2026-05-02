const { Client, RemoteAuth, LocalAuth } = require('whatsapp-web.js');
const { MongoStore } = require('wwebjs-mongo');
const mongoose = require('mongoose');
const path = require('path');
const fs = require('fs');
require('dotenv').config({ path: path.join(__dirname, '../.env') });
require('dotenv').config();

// ANTI-CRASH SHIELD: Catch the buggy Windows zip errors
process.on('uncaughtException', (err) => {
    if (err.message.includes('ENOENT') && err.message.includes('.zip')) {
        console.log('⏳ Windows Sync Glitch (Ignored) - Still working...');
    } else {
        console.error('❌ UNCAUGHT ERROR:', err);
        // Don't exit if it's just a sync issue
    }
});

async function setup() {
    const mongoUri = process.env.MONGO_DB_URI;
    
    if (!mongoUri) {
        console.error('❌ MONGO_DB_URI missing');
        return;
    }

    console.log('Connecting to MongoDB (database: indiabixauto)...');
    await mongoose.connect(mongoUri);
    const store = new MongoStore({ mongoose: mongoose, collection: 'whatsapp_sessions' });

    const clientId = "whatsapp-bot";

    // STAGE 0: PURGE OLD DATA
    console.log('🧹 STAGE 0: Purging old session from MongoDB for a fresh start...');
    const SessionModel = mongoose.model('WhatsAppSession', new mongoose.Schema({
        id: String,
        session: Buffer
    }, { collection: 'whatsapp_sessions' }));
    await SessionModel.deleteOne({ id: clientId });
    console.log('✅ MongoDB is clean.');

    const client = new Client({
        authStrategy: new RemoteAuth({
            store: store,
            backupSyncIntervalMs: 600000,
            clientId: clientId,
            dataPath: './.wwebjs_auth' 
        }),
        puppeteer: {
            headless: false,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-extensions',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ],
            userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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

    client.on('ready', async () => {
        console.log('\n✅ WhatsApp is ready!');
        console.log('⏳ STAGE 2: Waiting 20 seconds for session to settle...');
        
        await new Promise(resolve => setTimeout(resolve, 20000));

        console.log('🛑 Closing browser to unlock files...');
        try {
            await client.destroy();
            console.log('🔓 Files unlocked.');
        } catch (e) {
            console.log('⚠️ Note: Browser closed with warning (this is fine).');
        }

        // Wait a few seconds for Windows to release the locks
        await new Promise(resolve => setTimeout(resolve, 5000));

        console.log('🚀 STAGE 3: Cleaning and Syncing to MongoDB...');

        try {
            const sessionDir = path.join(__dirname, `.wwebjs_auth/RemoteAuth-${clientId}`);

            // 1. CLEAN JUNK
            console.log('  🧹 Cleaning browser cache...');
            const junkFolders = ['Default/Cache', 'Default/Code Cache', 'Default/GPUCache', 'Default/Service Worker/CacheStorage', 'Default/Service Worker/ScriptCache'];
            junkFolders.forEach(folder => {
                const fullPath = path.join(sessionDir, folder);
                if (fs.existsSync(fullPath)) {
                    try {
                        fs.rmSync(fullPath, { recursive: true, force: true });
                    } catch (e) {
                        console.log(`    ⚠️ Could not clean ${folder} (skipping)`);
                    }
                }
            });

            // 2. ZIP MANUALLY
            const archiver = require('archiver');
            const chunks = [];
            const archive = archiver('zip', { zlib: { level: 9 } });
            archive.on('data', (chunk) => chunks.push(chunk));
            
            console.log('  📦 Zipping session...');
            archive.directory(sessionDir, false);
            await archive.finalize();
            const buffer = Buffer.concat(chunks);

        // Find the collection
        const SessionModel = mongoose.models.WhatsAppSession || mongoose.model('WhatsAppSession', new mongoose.Schema({
            id: String,
            session: Buffer
        }, { collection: 'whatsapp_sessions' }));

        console.log('  📤 Uploading to "whatsapp_sessions" collection...');
        await SessionModel.findOneAndUpdate({ id: clientId }, { session: buffer }, { upsert: true });

            console.log('\n' + '='*60);
            console.log('🌟 SUCCESS: YOUR FRESH SESSION IS NOW IN MONGODB!');
            console.log('You can now close this window. Your automation is ready.');
            console.log('='*60 + '\n');
            
            setTimeout(() => process.exit(0), 2000);
        } catch (err) {
            console.error('❌ Sync failed:', err);
        }
    });

    console.log('Starting client initialization...');
    client.initialize();
}

setup().catch(err => {
    console.error('Setup error:', err);
    process.exit(1);
});
